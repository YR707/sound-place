// 进程白名单过滤
//
// 功能:枚举当前系统混音中各进程的音频会话,判断白名单中的游戏进程是否在发声
//
// 重要说明(关于 v1 简化):
// 真正的"按进程过滤音频流"需要用 AudioClient::new_application_loopback_client(),
// 但这要求每次切换进程都重新初始化 AudioClient,且 Win10 1903+ 才支持。
//
// v1 采用更简单的策略:
// - 仍抓全混音(loopback)
// - 用 IAudioSessionEnumerator 检测白名单进程是否在发声
// - 如果没有任何白名单进程在发声,丢弃这批数据(不写入 ring buffer)
// - 这样实现"只听游戏进程"的效果,同时无需重启 AudioClient
//
// 备注:wasapi crate 0.17+ 暴露了 AudioSessionEnumerator,但 API 较底层。
// 为保持依赖最小化,这里直接用 windows-sys 调 COM。

use std::ffi::c_void;
use std::ptr;

use log::{debug, warn};
use windows_sys::Win32::Media::Audio::*;
use windows_sys::Win32::System::Com::CoTaskMemFree;
use windows_sys::Win32::System::Threading::OpenProcess;
use windows_sys::Win32::System::ProcessStatus::{EnumProcessModules, GetModuleBaseNameW};

const PROCESS_QUERY_LIMITED_INFORMATION: u32 = 0x1000;

/// 进程白名单过滤器
///
/// 持有进程名列表(小写,无 .exe 后缀),如 ["huntshowdown", "r6siege"]
pub struct SessionFilter {
    /// 白名单进程名(已小写化,不含扩展名)
    process_names: Vec<String>,
    /// 是否启用过滤(空列表 => 不启用,抓全混音)
    enabled: bool,
}

impl SessionFilter {
    /// 创建过滤器
    ///
    /// process_names: 进程名列表(可带或不带 .exe 后缀,大小写不敏感)
    pub fn new(process_names: &[String]) -> Self {
        let normalized: Vec<String> = process_names
            .iter()
            .map(|s| {
                let lower = s.to_lowercase();
                lower.strip_suffix(".exe").unwrap_or(&lower).to_string()
            })
            .filter(|s| !s.is_empty())
            .collect();

        Self {
            enabled: !normalized.is_empty(),
            process_names: normalized,
        }
    }

    /// 是否启用过滤
    pub fn is_enabled(&self) -> bool {
        self.enabled
    }

    /// 查询当前是否有白名单进程正在发声
    ///
    /// 返回 true 表示应该处理音频;false 表示应该丢弃
    ///
    /// 错误处理:任何 COM 调用失败都返回 true(fallback 到不过滤,避免漏数据)
    pub fn should_process_audio(&self) -> bool {
        if !self.enabled {
            return true;
        }

        match self.check_whitelist_processes_active() {
            Ok(active) => active,
            Err(e) => {
                // 出错时 fallback:不过滤
                warn!("进程过滤查询失败,降级到全混音模式: {e}");
                true
            }
        }
    }

    /// 枚举音频会话,检查白名单进程是否活跃
    fn check_whitelist_processes_active(&self) -> Result<bool, String> {
        unsafe {
            // 创建设备枚举器
            let mut enumerator: *mut IMMDeviceEnumerator = ptr::null_mut();
            let hr = CoCreateInstance(
                &CLSID_MMDeviceEnumerator,
                ptr::null_mut(),
                1, // CLSCTX_INPROC_SERVER
                &IID_IMMDeviceEnumerator,
                &mut enumerator as *mut _ as *mut *mut c_void,
            );
            if hr != 0 {
                return Err(format!("CoCreateInstance 失败: 0x{:08X}", hr));
            }

            // 激活 IAudioSessionManager2
            let mut device: *mut IMMDevice = ptr::null_mut();
            let hr = (*enumerator).GetDefaultAudioEndpoint(eRender, eConsole, &mut device);
            if hr != 0 {
                (*enumerator).Release();
                return Err(format!("GetDefaultAudioEndpoint 失败: 0x{:08X}", hr));
            }

            let mut session_manager: *mut IAudioSessionManager2 = ptr::null_mut();
            let hr = (*device).Activate(
                &IID_IAudioSessionManager2,
                0,
                ptr::null_mut(),
                &mut session_manager as *mut _ as *mut *mut c_void,
            );
            (*device).Release();
            (*enumerator).Release();

            if hr != 0 {
                return Err(format!("Activate IAudioSessionManager2 失败: 0x{:08X}", hr));
            }

            // 枚举会话
            let mut session_enum: *mut IAudioSessionEnumerator = ptr::null_mut();
            let hr = (*session_manager).GetSessionEnumerator(&mut session_enum);
            if hr != 0 {
                (*session_manager).Release();
                return Err(format!("GetSessionEnumerator 失败: 0x{:08X}", hr));
            }

            let mut count: i32 = 0;
            let hr = (*session_enum).GetCount(&mut count);
            if hr != 0 {
                (*session_enum).Release();
                (*session_manager).Release();
                return Err(format!("GetCount 失败: 0x{:08X}", hr));
            }

            debug!("发现 {count} 个音频会话");

            let mut found = false;
            for i in 0..count {
                if self.check_session(&mut (*session_enum), i) {
                    found = true;
                    break;
                }
            }

            (*session_enum).Release();
            (*session_manager).Release();
            Ok(found)
        }
    }

    /// 检查单个会话的进程是否在白名单中
    unsafe fn check_session(
        &self,
        session_enum: &mut IAudioSessionEnumerator,
        index: i32,
    ) -> bool {
        let mut session: *mut IAudioSessionControl = ptr::null_mut();
        let hr = (*session_enum).GetSession(index, &mut session);
        if hr != 0 {
            return false;
        }

        // 查询 IAudioSessionControl2 以获取进程 ID
        let mut session2: *mut IAudioSessionControl2 = ptr::null_mut();
        let hr = (*session).QueryInterface(
            &IID_IAudioSessionControl2,
            &mut session2 as *mut _ as *mut *mut c_void,
        );
        (*session).Release();

        if hr != 0 {
            return false;
        }

        let mut pid: u32 = 0;
        let hr = (*session2).GetProcessId(&mut pid);
        (*session2).Release();

        if hr != 0 || pid == 0 {
            return false;
        }

        // 获取进程名
        let process_name = match get_process_name(pid) {
            Some(name) => name,
            None => return false,
        };

        let lower = process_name.to_lowercase();
        let stem = lower.strip_suffix(".exe").unwrap_or(&lower);

        let matched = self.process_names.iter().any(|p| p == stem);
        if matched {
            debug!("白名单进程活跃: {} (pid={})", process_name, pid);
        }
        matched
    }
}

/// 通过 PID 获取进程名
fn get_process_name(pid: u32) -> Option<String> {
    unsafe {
        let handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid);
        if handle.is_null() {
            return None;
        }

        // 先用 0 作 cbSize 查询所需大小
        let mut needed: u32 = 0;
        let _ = EnumProcessModules(handle, ptr::null_mut(), 0, &mut needed);

        if needed == 0 {
            windows_sys::Win32::Foundation::CloseHandle(handle);
            return None;
        }

        let mut modules: [u64; 1024] = [0; 1024];
        let mut cb_needed: u32 = 0;
        let ok = EnumProcessModules(
            handle,
            modules.as_mut_ptr(),
            (modules.len() * std::mem::size_of::<u64>()) as u32,
            &mut cb_needed,
        );

        if ok == 0 {
            windows_sys::Win32::Foundation::CloseHandle(handle);
            return None;
        }

        // 取第一个模块(主模块)的名字
        let mut name_buf: [u16; 260] = [0; 260];
        let len = GetModuleBaseNameW(handle, modules[0] as *const c_void, name_buf.as_mut_ptr(), name_buf.len() as u32);
        windows_sys::Win32::Foundation::CloseHandle(handle);

        if len == 0 {
            return None;
        }

        let name = String::from_utf16_lossy(&name_buf[..len as usize]);
        Some(name)
    }
}
