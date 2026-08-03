"""Python ↔ WebEngine JS 桥：注入脚本并执行 API。

注意：部分 Qt WebEngine 版本对 runJavaScript 返回的 Promise 回调为 null，
因此异步结果一律写入 window.__qqBridgePending，再由 Python 轮询读取。
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineScript


JS_PATH = Path(__file__).with_name('qq_api.js')


class QQBridge(QObject):
    """在 QWebEnginePage 上注入并调用 window.__QQAlbumAPI。"""

    log = Signal(str)

    def __init__(self, page: QWebEnginePage, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.page = page
        self._api_js = JS_PATH.read_text(encoding='utf-8')
        self._injected = False

    def inject_api(self, callback: Callable[[bool], None] | None = None) -> None:
        def done(result: Any = None) -> None:
            self._injected = True
            if callback:
                callback(True)

        # ApplicationWorld = 主页面 JS 上下文，才能访问 GroupZone
        try:
            self.page.runJavaScript(
                self._api_js,
                QWebEngineScript.ScriptWorldId.MainWorld,
                done,
            )
        except TypeError:
            # 旧签名无 worldId
            self.page.runJavaScript(self._api_js, done)

    def _run_js(self, script: str, callback: Callable[[Any], None]) -> None:
        try:
            self.page.runJavaScript(
                script,
                QWebEngineScript.ScriptWorldId.MainWorld,
                callback,
            )
        except TypeError:
            self.page.runJavaScript(script, callback)

    def check_ready(self, callback: Callable[[bool], None]) -> None:
        expr = (
            "(function(){try{"
            "if(!window.__QQAlbumAPI){return false;}"
            "return !!window.__QQAlbumAPI.isReady();"
            "}catch(e){return false;}})()"
        )

        def after_inject(_=None) -> None:
            self._run_js(expr, lambda ready: callback(bool(ready)))

        self.inject_api(after_inject)

    def diagnose(self, callback: Callable[[dict], None]) -> None:
        """诊断页面环境，便于排查拉取失败。"""
        expr = (
            "(function(){try{return JSON.stringify({"
            "href: location.href,"
            "hasGroupZone: !!window.GroupZone,"
            "hasGPHOTO: !!(window.GroupZone&&GroupZone.GPHOTO),"
            "hasLogic: !!(window.GroupZone&&GroupZone.GPHOTO&&GroupZone.GPHOTO.logic),"
            "hasGetAlbumList: !!(window.GroupZone&&GroupZone.GPHOTO&&GroupZone.GPHOTO.logic"
            "&&typeof GroupZone.GPHOTO.logic.getAlbumList==='function'),"
            "hasSeajs: !!window.seajs,"
            "hasAPI: !!window.__QQAlbumAPI,"
            "apiReady: !!(window.__QQAlbumAPI&&window.__QQAlbumAPI.isReady&&window.__QQAlbumAPI.isReady())"
            "});}catch(e){return JSON.stringify({error:String(e)});}})()"
        )

        def after(_=None) -> None:
            self._run_js(expr, lambda raw: callback(json.loads(raw) if raw else {'error': 'empty diagnose'}))

        self.inject_api(after)

    def _call_async(
        self,
        js_call: str,
        callback: Callable[[Any], None],
        timeout_ms: int = 120_000,
    ) -> None:
        token = uuid.uuid4().hex
        starter = f"""
        (function(){{
          var token = {json.dumps(token)};
          window.__qqBridgePending = window.__qqBridgePending || {{}};
          window.__qqBridgePending[token] = {{status: 'running'}};
          (async function(){{
            try {{
              if (!window.__QQAlbumAPI) throw new Error('API未注入');
              if (!window.__QQAlbumAPI.isReady()) throw new Error('相册页面未就绪(GroupZone不可用)');
              var r = await {js_call};
              window.__qqBridgePending[token] = {{
                status: 'done',
                payload: JSON.stringify({{ok: true, data: r}})
              }};
            }} catch (e) {{
              var msg = (e && (e.message || e.msg || e.code)) ? String(e.message || e.msg || e.code) : String(e);
              window.__qqBridgePending[token] = {{
                status: 'done',
                payload: JSON.stringify({{ok: false, error: msg}})
              }};
            }}
          }})();
          return token;
        }})()
        """
        poll_expr = f"""
        (function(){{
          var token = {json.dumps(token)};
          var p = window.__qqBridgePending && window.__qqBridgePending[token];
          if (!p) return JSON.stringify({{status: 'missing'}});
          if (p.status !== 'done') return JSON.stringify({{status: 'running'}});
          var payload = p.payload;
          try {{ delete window.__qqBridgePending[token]; }} catch (e) {{}}
          return JSON.stringify({{status: 'done', payload: payload}});
        }})()
        """

        elapsed = {'ms': 0}
        timer = QTimer(self)
        timer.setInterval(300)

        def finish(result: dict) -> None:
            timer.stop()
            timer.deleteLater()
            callback(result)

        def on_poll(raw: Any) -> None:
            try:
                if not raw:
                    # 继续等，可能暂时空
                    return
                info = json.loads(raw) if isinstance(raw, str) else raw
                status = info.get('status')
                if status == 'running':
                    return
                if status == 'missing':
                    finish({'ok': False, 'error': '任务丢失(页面可能已刷新)，请回到登录页重试'})
                    return
                if status == 'done':
                    payload = info.get('payload') or ''
                    if not payload:
                        finish({'ok': False, 'error': 'empty result'})
                        return
                    finish(json.loads(payload))
                    return
            except Exception as exc:  # noqa: BLE001
                finish({'ok': False, 'error': str(exc)})

        def tick() -> None:
            elapsed['ms'] += 300
            if elapsed['ms'] >= timeout_ms:
                finish({'ok': False, 'error': f'拉取超时({timeout_ms // 1000}s)，请确认仍在相册页且已登录'})
                return
            self._run_js(poll_expr, on_poll)

        timer.timeout.connect(tick)

        def after_inject(_=None) -> None:
            def on_started(raw: Any) -> None:
                if not raw:
                    # 即便 starter 返回空，也可能已启动，继续轮询
                    self.log.emit('警告: 启动脚本无返回值，继续轮询结果')
                timer.start()
                tick()

            self._run_js(starter, on_started)

        self.inject_api(after_inject)

    def list_albums(self, callback: Callable[[Any], None]) -> None:
        self._call_async('window.__QQAlbumAPI.listAlbums()', callback, timeout_ms=120_000)

    def get_album_zip_url(self, album_id: str, title: str, callback: Callable[[Any], None]) -> None:
        aid = json.dumps(album_id)
        t = json.dumps(title)
        self._call_async(f'window.__QQAlbumAPI.getAlbumZipUrl({aid},{t})', callback)

    def get_batch_zip_url(
        self,
        album_id: str,
        title: str,
        photo_ids: list[str],
        callback: Callable[[Any], None],
    ) -> None:
        aid = json.dumps(album_id)
        t = json.dumps(title)
        ids = json.dumps(photo_ids, ensure_ascii=False)
        self._call_async(f'window.__QQAlbumAPI.getBatchZipUrl({aid},{t},{ids})', callback)

    def list_photos(self, album_id: str, callback: Callable[[Any], None]) -> None:
        aid = json.dumps(album_id)
        self._call_async(f'window.__QQAlbumAPI.listPhotos({aid})', callback, timeout_ms=600_000)


class LoginWatcher(QObject):
    """轮询检测登录就绪；若页面已打开但 API 长期不可用则请求自动刷新。"""

    ready_changed = Signal(bool)
    status = Signal(str)
    need_refresh = Signal()

    def __init__(self, bridge: QQBridge, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        self._timer = QTimer(self)
        self._timer.setInterval(1500)
        self._timer.timeout.connect(self._tick)
        self._ready = False
        self._not_ready_ticks = 0
        self._auto_refresh_count = 0
        self._max_auto_refresh = 3
        # 加载后约 6 秒仍未就绪才自动刷新，避免登录过程中误刷
        self._refresh_after_ticks = 4
        self._refreshing = False

    def start(self) -> None:
        self._not_ready_ticks = 0
        self._refreshing = False
        self._timer.start()
        self._tick()

    def stop(self) -> None:
        self._timer.stop()

    def reset_session(self) -> None:
        """打开新群 / 重新进入时重置自动刷新计数。"""
        self._ready = False
        self._not_ready_ticks = 0
        self._auto_refresh_count = 0
        self._refreshing = False

    def notify_reload_started(self) -> None:
        """页面开始刷新时调用，暂停计数避免连环刷新。"""
        self._refreshing = True
        self._not_ready_ticks = 0

    def _tick(self) -> None:
        self.bridge.check_ready(self._on_ready)

    def _on_ready(self, ready: bool) -> None:
        if ready:
            self._not_ready_ticks = 0
            self._refreshing = False
            if not self._ready:
                self._ready = True
                self.ready_changed.emit(True)
            self.status.emit('已登录，可以开始处理')
            return

        if self._ready:
            self._ready = False
            self.ready_changed.emit(False)

        if self._refreshing:
            self.status.emit('正在刷新页面，等待相册接口就绪…')
            return

        self._not_ready_ticks += 1
        if (
            self._not_ready_ticks >= self._refresh_after_ticks
            and self._auto_refresh_count < self._max_auto_refresh
        ):
            self._auto_refresh_count += 1
            self._not_ready_ticks = 0
            self._refreshing = True
            self.status.emit(
                f'页面状态未就绪，正在自动刷新（{self._auto_refresh_count}/{self._max_auto_refresh}）…'
            )
            self.need_refresh.emit()
            return

        if self._auto_refresh_count >= self._max_auto_refresh:
            self.status.emit('仍未就绪，请手动点「刷新页面」或确认已登录')
        else:
            self.status.emit('等待登录或页面就绪…')
