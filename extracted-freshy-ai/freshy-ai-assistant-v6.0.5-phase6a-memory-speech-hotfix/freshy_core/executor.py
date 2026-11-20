import sys
import os
import platform
import subprocess
import webbrowser
import threading
import time
from datetime import datetime
from typing import Dict, Any, Tuple
from urllib.parse import urlparse

class CommandExecutor:
    """
    Strict allowlisted action executor for Freshy AI.
    Prevents execution of arbitrary or dangerous system commands or unallowed domains.
    """
    
    ALLOWLISTED_APPS = {
        "notepad": {
            "windows_cmd": "notepad.exe",
            "cross_cmd": "notepad",
            "display_name": "Notepad"
        },
        "calculator": {
            "windows_cmd": "calc.exe",
            "cross_cmd": "calc",
            "display_name": "Calculator"
        }
    }
    
    ALLOWED_DOMAINS = [
        "google.com", "www.google.com",
        "youtube.com", "www.youtube.com",
        "github.com", "www.github.com",
        "wikipedia.org", "www.wikipedia.org"
    ]

    @staticmethod
    def _foreground_windows_app(
        process: subprocess.Popen, title_hint: str
    ) -> None:
        """
        Promote a newly launched allowlisted app to the Windows foreground.

        Calculator can be hosted by ApplicationFrameHost, so a title fallback
        is used when the visible window does not belong to calc.exe. This is
        best-effort and runs off the API thread.
        """

        if platform.system().lower() != "windows":
            return
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            target_pid = int(process.pid)
            normalized_hint = title_hint.casefold()
            deadline = time.monotonic() + 4.0

            while time.monotonic() < deadline:
                pid_matches = []
                title_matches = []

                @ctypes.WINFUNCTYPE(
                    wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
                )
                def enum_callback(hwnd, _lparam):
                    if not user32.IsWindowVisible(hwnd):
                        return True
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length <= 0:
                        return True
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buffer, length + 1)
                    title = buffer.value.strip()
                    if not title:
                        return True
                    window_pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(
                        hwnd, ctypes.byref(window_pid)
                    )
                    if int(window_pid.value) == target_pid:
                        pid_matches.append(hwnd)
                    elif (
                        normalized_hint
                        and normalized_hint in title.casefold()
                    ):
                        title_matches.append(hwnd)
                    return True

                user32.EnumWindows(enum_callback, 0)
                candidates = pid_matches or title_matches
                if candidates:
                    hwnd = candidates[0]
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.BringWindowToTop(hwnd)
                    user32.SetForegroundWindow(hwnd)
                    return
                time.sleep(0.1)
        except Exception:
            # Focus promotion must never turn a successful launch into a
            # failed command.
            return

    def _is_domain_allowed(self, url: str) -> Tuple[bool, str]:
        """
        Safely parses a URL and checks if its netloc matches ALLOWED_DOMAINS or allowed subdomains.
        """
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        hostname = (parsed.hostname or "").lower().rstrip(".")

        if scheme not in {"http", "https"} or not hostname:
            return False, "invalid_url"

        for domain in self.ALLOWED_DOMAINS:
            if hostname == domain or hostname.endswith("." + domain):
                return True, hostname
        return False, hostname

    def execute_intent(self, intent_name: str, parameters: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Executes an intent based strictly on the safe allowlist.
        Returns: (success: bool, response_message: str, details: dict)
        """
        if intent_name == "GREETING":
            return True, "Hello! I am Freshy, your AI assistant. How can I assist you today?", {"action": "GREETING"}
            
        elif intent_name == "TIME_DATE":
            now = datetime.now()
            formatted_time = now.strftime("%I:%M %p")
            formatted_date = now.strftime("%A, %B %d, %Y")
            msg = f"The current time is {formatted_time} on {formatted_date}."
            return True, msg, {"time": formatted_time, "date": formatted_date, "action": "TIME_DATE"}
            
        elif intent_name == "OPEN_APP":
            app_name = str(parameters.get("app_name", "")).lower()
            if app_name not in self.ALLOWLISTED_APPS:
                return False, f"Security Block: '{app_name}' is not in Freshy's allowlisted applications.", {"allowed": list(self.ALLOWLISTED_APPS.keys())}
                
            app_info = self.ALLOWLISTED_APPS[app_name]
            is_windows = platform.system().lower() == "windows"
            
            try:
                if is_windows:
                    process = subprocess.Popen([app_info["windows_cmd"]])
                    threading.Thread(
                        target=self._foreground_windows_app,
                        args=(process, app_info["display_name"]),
                        daemon=True,
                        name=f"FreshyFocus{app_info['display_name']}",
                    ).start()
                    return True, f"Opened {app_info['display_name']} successfully.", {"app": app_name, "status": "launched_windows"}
                else:
                    return True, f"[Simulation] Opened {app_info['display_name']} (Running on non-Windows host: {platform.system()}).", {"app": app_name, "status": "simulated_non_windows"}
            except Exception as e:
                return False, f"Failed to launch {app_info['display_name']}: {str(e)}", {"error": str(e)}
                
        elif intent_name == "OPEN_WEBSITE":
            raw_url = str(parameters.get("url", "https://www.google.com")).strip()
            lowered_url = raw_url.lower()
            if not lowered_url.startswith("http://") and not lowered_url.startswith("https://"):
                url = "https://" + raw_url
            else:
                url = raw_url
                
            allowed, netloc = self._is_domain_allowed(url)
            if not allowed:
                return False, f"Security Block: Domain '{netloc}' is not in Freshy's allowlisted websites.", {"url": url, "domain": netloc, "allowed_domains": self.ALLOWED_DOMAINS}

            try:
                webbrowser.open(url)
                return True, f"Opening {url} in your default browser.", {"url": url, "action": "OPEN_WEBSITE"}
            except Exception as e:
                return False, f"Failed to open website {url}: {str(e)}", {"error": str(e)}
                
        elif intent_name == "UNKNOWN":
            query = parameters.get("query", "")
            if not str(query).strip():
                return False, "Message cannot be empty.", {"error": "empty_query"}
            return False, (
                f"Freshy heard: '{query}'. In Phase 3, try saying "
                "'Hello Freshy' before a command, or ask for the time, "
                "Notepad, Calculator, Google, YouTube, GitHub, or Wikipedia."
            ), {"action": "UNKNOWN_FALLBACK"}
            
        else:
            return False, f"Unknown or unsupported intent: '{intent_name}'", {"intent": intent_name}
