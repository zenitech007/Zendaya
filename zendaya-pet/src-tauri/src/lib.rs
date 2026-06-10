use serde::Serialize;

#[derive(Serialize)]
pub struct WindowInfo {
    title: String,
    x: i32,
    y: i32,
    width: i32,
    height: i32,
}

#[cfg(windows)]
#[tauri::command]
fn get_active_windows() -> Vec<WindowInfo> {
    use windows::Win32::Foundation::{BOOL, HWND, LPARAM, RECT};
    use windows::Win32::UI::WindowsAndMessaging::{
        EnumWindows, GetWindowRect, GetWindowTextW, IsWindowVisible, GetWindowLongW, GWL_EXSTYLE, WS_EX_TOOLWINDOW
    };

    let mut windows: Vec<WindowInfo> = Vec::new();

    unsafe extern "system" fn enum_window(hwnd: HWND, lparam: LPARAM) -> BOOL {
        let windows = &mut *(lparam.0 as *mut Vec<WindowInfo>);
        
        if IsWindowVisible(hwnd).as_bool() {
            // Filter out tool windows and invisible things
            let ex_style = GetWindowLongW(hwnd, GWL_EXSTYLE) as u32;
            if (ex_style & WS_EX_TOOLWINDOW.0) == 0 {
                let mut title: [u16; 512] = [0; 512];
                let len = GetWindowTextW(hwnd, &mut title);
                let title_str = String::from_utf16_lossy(&title[..len as usize]);
                
                // Exclude the pet window itself and background managers
                if !title_str.is_empty() && title_str != "Program Manager" && title_str != "Zendaya Pet" {
                    let mut rect = RECT::default();
                    if GetWindowRect(hwnd, &mut rect).is_ok() {
                        windows.push(WindowInfo {
                            title: title_str,
                            x: rect.left,
                            y: rect.top,
                            width: rect.right - rect.left,
                            height: rect.bottom - rect.top,
                        });
                    }
                }
            }
        }
        BOOL::from(true)
    }

    unsafe {
        let _ = EnumWindows(Some(enum_window), LPARAM(&mut windows as *mut _ as isize));
    }
    
    windows
}

#[cfg(not(windows))]
#[tauri::command]
fn get_active_windows() -> Vec<WindowInfo> {
    Vec::new()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![get_active_windows])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
