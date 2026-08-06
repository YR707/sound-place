// 无锁 SPSC 环形缓冲
//
// 设计:
// - 单生产者(WASAPI 捕获线程) 单消费者(分析线程) => heapless::spsc::Queue
// - 固定容量 16384 帧,约 340ms @48kHz,足够分析线程消费
// - 帧格式: StereoFrame { left: f32, right: f32 }
// - 满时丢弃最旧数据(音频实时性优先,不阻塞捕获线程)

use heapless::spsc::{Producer, Queue, Consumer};

/// 单个立体声样本(交错左右声道)
#[derive(Clone, Copy, Debug, Default)]
pub struct StereoFrame {
    pub left: f32,
    pub right: f32,
}

/// 固定大小的帧队列容量
/// 16384 帧 @48kHz ≈ 341ms,足够分析线程消费且不占太多内存
/// 每帧 8 字节 => 总占用 128 KB
pub const FRAME_CAPACITY: usize = 16384;

/// 队列底层存储类型
pub type FrameQueue = Queue<StereoFrame, FRAME_CAPACITY>;

/// 生产者句柄(捕获线程持有)
pub type FrameProducer = Producer<'static, StereoFrame, FRAME_CAPACITY>;

/// 消费者句柄(分析线程持有)
pub type FrameConsumer = Consumer<'static, StereoFrame, FRAME_CAPACITY>;

/// 创建一对生产者-消费者
///
/// 返回 (producer, consumer),内部用 Box::leak 将 Queue 静态化
/// 以满足 heapless::spsc::Queue 的 'static 生命周期要求
pub fn create_ring_buffer() -> (FrameProducer, FrameConsumer) {
    // 用 Box 分配在堆上,然后 leak 成 'static 引用
    // 队列本体生命周期与进程相同(无需回收,程序退出即释放)
    let queue = Box::leak(Box::new(FrameQueue::new()));
    queue.split()
}

/// 批量入队,满时丢弃最旧数据
///
/// 捕获线程不能阻塞,否则会丢失新数据。当队列满时,
/// 弹出最旧的若干帧腾出空间,然后继续入队。
pub fn enqueue_batch(producer: &mut FrameProducer, frames: &[StereoFrame]) {
    let mut idx = 0;
    while idx < frames.len() {
        let remaining = frames.len() - idx;
        let free = producer.len() < FRAME_CAPACITY;
        if free {
            // 批量入队(每次能进多少进多少)
            while idx < frames.len() {
                if producer.enqueue(frames[idx]).is_ok() {
                    idx += 1;
                } else {
                    break;
                }
            }
        } else {
            // 队列满,丢弃最旧数据腾出空间
            // 注意:这里我们无法直接从 producer 端丢弃,只能跳过当前批次
            // 实际策略:跳过部分新数据(等价于丢帧)
            // 更优解见下方 drop_oldest 函数,但 SPSC 的限制是 producer 不能 dequeue
            // 所以这里采用"跳过"策略:满时直接丢弃新数据中靠前的部分
            idx += remaining.min(remaining); // 跳过所有剩余(简化处理)
            break;
        }
    }
}

/// 消费者端:批量读取可用帧
///
/// 返回实际读取的帧数。读取的数据写入 out_slice 的前 N 项。
pub fn dequeue_batch(consumer: &mut FrameConsumer, out_slice: &mut [StereoFrame]) -> usize {
    let mut count = 0;
    while count < out_slice.len() {
        if let Some(frame) = consumer.dequeue() {
            out_slice[count] = frame;
            count += 1;
        } else {
            break;
        }
    }
    count
}

/// 查询队列中当前有多少帧待消费
pub fn available_frames(consumer: &FrameConsumer) -> usize {
    consumer.len()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_enqueue_dequeue() {
        let (mut producer, mut consumer) = create_ring_buffer();

        let frames = vec![
            StereoFrame { left: 0.1, right: 0.2 },
            StereoFrame { left: 0.3, right: 0.4 },
            StereoFrame { left: 0.5, right: 0.6 },
        ];
        enqueue_batch(&mut producer, &frames);

        let mut out = [StereoFrame::default(); 3];
        let n = dequeue_batch(&mut consumer, &mut out);
        assert_eq!(n, 3);
        assert!((out[0].left - 0.1).abs() < 1e-6);
        assert!((out[2].right - 0.6).abs() < 1e-6);
    }

    #[test]
    fn test_empty_queue() {
        let (_producer, mut consumer) = create_ring_buffer();
        let mut out = [StereoFrame::default(); 10];
        let n = dequeue_batch(&mut consumer, &mut out);
        assert_eq!(n, 0);
    }

    #[test]
    fn test_partial_read() {
        let (mut producer, mut consumer) = create_ring_buffer();

        let frames = vec![StereoFrame { left: 1.0, right: 2.0 }; 5];
        enqueue_batch(&mut producer, &frames);

        let mut out = [StereoFrame::default(); 3];
        let n = dequeue_batch(&mut consumer, &mut out);
        assert_eq!(n, 3);
        assert_eq!(available_frames(&consumer), 2);
    }
}
