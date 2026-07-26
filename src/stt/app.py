from __future__ import annotations

import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .dictation import DictationConfig, DictationSession
from .settings import (
    DOUBLE_TAP_MODIFIERS,
    MODIFIER_KEY_CODES,
    MODIFIER_MASK,
    ActivationMode,
    AppSettings,
    HotkeyBinding,
    ShortcutKind,
    load_settings,
    save_settings,
)
from .terms import load_terms, save_terms

StatusCallback = Callable[[str, str | None], None]


class EngineCoordinator:
    def __init__(self, on_status: StatusCallback) -> None:
        self._on_status = on_status
        self._settings: AppSettings | None = None
        self._session: DictationSession | None = None
        self._session_token: object | None = None
        self._session_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._changed = threading.Event()
        self._shutdown = threading.Event()
        self._manager = threading.Thread(
            target=self._manage,
            name="stt-engine-manager",
            daemon=True,
        )
        self._manager.start()

    def apply(self, settings: AppSettings | None) -> None:
        with self._lock:
            self._settings = settings
        self._changed.set()

    def toggle_recording(self) -> None:
        with self._lock:
            session = self._session
        if session is not None:
            session.toggle_recording()

    def shutdown(self) -> None:
        self._shutdown.set()
        self._changed.set()
        self._manager.join(timeout=4)

    def _manage(self) -> None:
        while True:
            self._changed.wait()
            self._changed.clear()
            self._stop_session()
            if self._shutdown.is_set():
                return

            with self._lock:
                settings = self._settings
            if settings is None:
                self._on_status("paused", None)
                continue

            session_token = object()

            def on_session_status(
                status: str,
                detail: str | None,
                token: object = session_token,
            ) -> None:
                self._session_status(token, status, detail)

            session = DictationSession(
                DictationConfig(settings=settings),
                on_status=on_session_status,
            )
            thread = threading.Thread(
                target=self._run_session,
                args=(
                    session,
                    session_token,
                ),
                name="stt-dictation",
                daemon=True,
            )
            with self._lock:
                self._session = session
                self._session_token = session_token
                self._session_thread = thread
            thread.start()

    def _run_session(
        self,
        session: DictationSession,
        session_token: object,
    ) -> None:
        try:
            session.run()
        except Exception as exc:  # noqa: BLE001
            self._session_status(
                session_token,
                "error",
                str(exc),
            )

    def _stop_session(self) -> None:
        with self._lock:
            session = self._session
            thread = self._session_thread
            self._session = None
            self._session_token = None
            self._session_thread = None
        if session is not None:
            session.stop()
        if thread is not None:
            thread.join(timeout=3)

    def _session_status(
        self,
        session_token: object,
        status: str,
        detail: str | None,
    ) -> None:
        with self._lock:
            is_current = self._session_token is session_token
        if is_current:
            self._on_status(status, detail)


def _configure_runtime() -> None:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
    os.environ.setdefault("DO_NOT_TRACK", "1")

    resources = os.environ.get("RESOURCEPATH")
    if resources:
        bundled_model = Path(resources) / "faster-whisper-base"
        if bundled_model.is_dir():
            os.environ["STT_MODEL_PATH"] = str(bundled_model)


def run() -> None:
    _configure_runtime()
    import AppKit
    import Foundation
    import objc

    class FlippedView(AppKit.NSView):
        def isFlipped(self) -> bool:
            return True

    class AppDelegate(Foundation.NSObject):
        engine: EngineCoordinator | None = None
        settings = AppSettings()
        window: Any = None
        status_item: Any = None
        status_menu_item: Any = None
        toggle_menu_item: Any = None
        status_label: Any = None
        status_dot: Any = None
        shortcut_button: Any = None
        mode_control: Any = None
        mode_help: Any = None
        shortcut_cancel_button: Any = None
        shortcut_confirm_button: Any = None
        shortcut_candidate: HotkeyBinding | None = None
        capture_pending_tap: HotkeyBinding | None = None
        capture_pending_tap_at = 0.0
        capture_chorded_modifiers = 0
        tab_control: Any = None
        general_view: Any = None
        terms_view: Any = None
        terms_input: Any = None
        terms_chip_view: Any = None
        terms: list[str]
        event_monitor: Any = None
        is_capturing = False
        needs_permission_retry = False
        permission_pane = "Privacy_Accessibility"

        def applicationDidFinishLaunching_(self, _notification: Any) -> None:
            self.settings = load_settings()
            self.terms = load_terms()
            self._build_main_menu()
            self._build_status_item()
            self._build_window()
            self._install_shortcut_capture()
            self.engine = EngineCoordinator(self._receive_status)
            self.engine.apply(self.settings)
            self.showSettings_(None)

        def applicationDidBecomeActive_(self, _notification: Any) -> None:
            if self.needs_permission_retry and self.engine is not None:
                self.engine.apply(self.settings)

        def applicationShouldHandleReopen_hasVisibleWindows_(
            self,
            _application: Any,
            _has_visible_windows: bool,
        ) -> bool:
            self.showSettings_(None)
            return True

        def applicationWillTerminate_(self, _notification: Any) -> None:
            if self.event_monitor is not None:
                AppKit.NSEvent.removeMonitor_(self.event_monitor)
                self.event_monitor = None
            if self.engine is not None:
                self.engine.shutdown()

        def windowShouldClose_(self, _sender: Any) -> bool:
            if self.is_capturing:
                self._finish_capture()
            AppKit.NSApp.terminate_(None)
            return False

        def hideSettings_(self, _sender: Any) -> None:
            self.window.orderOut_(None)
            AppKit.NSApp.setActivationPolicy_(
                AppKit.NSApplicationActivationPolicyAccessory
            )

        def showSettings_(self, _sender: Any) -> None:
            AppKit.NSApp.setActivationPolicy_(
                AppKit.NSApplicationActivationPolicyRegular
            )
            self.window.makeKeyAndOrderFront_(None)
            AppKit.NSApp.activateIgnoringOtherApps_(True)

        def toggleDictation_(self, _sender: Any) -> None:
            if self.engine is not None:
                self.engine.toggle_recording()

        def recordShortcut_(self, _sender: Any) -> None:
            if self.is_capturing:
                return
            self.is_capturing = True
            self.shortcut_candidate = None
            self.capture_pending_tap = None
            self.capture_pending_tap_at = 0.0
            self.capture_chorded_modifiers = 0
            self.shortcut_button.setFrame_(
                Foundation.NSMakeRect(288, 88, 104, 28)
            )
            self.shortcut_button.setTitle_("Press shortcut…")
            self.shortcut_cancel_button.setHidden_(False)
            self.shortcut_confirm_button.setHidden_(False)
            self.shortcut_confirm_button.setEnabled_(False)
            self.mode_help.setStringValue_("")
            if self.engine is not None:
                self.engine.apply(None)

        def cancelShortcut_(self, _sender: Any) -> None:
            self._finish_capture()

        def confirmShortcut_(self, _sender: Any) -> None:
            if self.shortcut_candidate is None:
                return
            mode = self.settings.activation_mode
            if self.shortcut_candidate.kind in {
                ShortcutKind.DOUBLE_MODIFIER,
                ShortcutKind.DOUBLE_KEY,
            }:
                mode = ActivationMode.TOGGLE
            self.settings = AppSettings(
                activation_mode=mode,
                hotkey=self.shortcut_candidate,
            )
            self._finish_capture(save=True)

        def modeChanged_(self, sender: Any) -> None:
            mode = (
                ActivationMode.TOGGLE
                if sender.selectedSegment() == 0
                else ActivationMode.HOLD
            )
            self.settings = AppSettings(
                activation_mode=mode,
                hotkey=self.settings.hotkey,
            ).normalized()
            self._persist_settings()

        def tabChanged_(self, sender: Any) -> None:
            show_general = sender.selectedSegment() == 0
            self.general_view.setHidden_(not show_general)
            self.terms_view.setHidden_(show_general)
            if not show_general:
                self.window.makeFirstResponder_(self.terms_input)

        def addTerm_(self, _sender: Any) -> None:
            term = self.terms_input.stringValue().strip()
            if not term:
                return
            if term.casefold() not in {value.casefold() for value in self.terms}:
                self.terms.append(term)
                save_terms(self.terms)
                self._refresh_terms()
            self.terms_input.setStringValue_("")

        def removeTerm_(self, sender: Any) -> None:
            index = int(sender.tag())
            if 0 <= index < len(self.terms):
                self.terms.pop(index)
                save_terms(self.terms)
                self._refresh_terms()

        def openPermissions_(self, _sender: Any) -> None:
            url = Foundation.NSURL.URLWithString_(
                "x-apple.systempreferences:com.apple.preference.security"
                f"?{self.permission_pane}"
            )
            AppKit.NSWorkspace.sharedWorkspace().openURL_(url)

        def quit_(self, _sender: Any) -> None:
            AppKit.NSApp.terminate_(None)

        @objc.python_method
        def _build_main_menu(self) -> None:
            main_menu = AppKit.NSMenu.alloc().init()

            app_item = AppKit.NSMenuItem.alloc().init()
            main_menu.addItem_(app_item)
            app_menu = AppKit.NSMenu.alloc().initWithTitle_("STT")
            settings_item = (
                AppKit.NSMenuItem.alloc()
                .initWithTitle_action_keyEquivalent_("Settings…", "showSettings:", ",")
            )
            settings_item.setTarget_(self)
            app_menu.addItem_(settings_item)
            app_menu.addItem_(AppKit.NSMenuItem.separatorItem())
            quit_item = (
                AppKit.NSMenuItem.alloc()
                .initWithTitle_action_keyEquivalent_("Quit", "quit:", "q")
            )
            quit_item.setTarget_(self)
            app_menu.addItem_(quit_item)
            app_item.setSubmenu_(app_menu)

            edit_item = AppKit.NSMenuItem.alloc().init()
            main_menu.addItem_(edit_item)
            edit_menu = AppKit.NSMenu.alloc().initWithTitle_("Edit")
            for title, action, key in (
                ("Cut", "cut:", "x"),
                ("Copy", "copy:", "c"),
                ("Paste", "paste:", "v"),
                ("Select All", "selectAll:", "a"),
            ):
                edit_menu.addItemWithTitle_action_keyEquivalent_(title, action, key)
            edit_item.setSubmenu_(edit_menu)
            AppKit.NSApp.setMainMenu_(main_menu)

        @objc.python_method
        def _build_status_item(self) -> None:
            self.status_item = (
                AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(
                    AppKit.NSVariableStatusItemLength
                )
            )
            button = self.status_item.button()
            button.setImage_(
                AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                    "waveform",
                    "STT",
                )
            )

            menu = AppKit.NSMenu.alloc().init()
            self.status_menu_item = (
                AppKit.NSMenuItem.alloc()
                .initWithTitle_action_keyEquivalent_("Initializing…", None, "")
            )
            self.status_menu_item.setEnabled_(False)
            menu.addItem_(self.status_menu_item)
            menu.addItem_(AppKit.NSMenuItem.separatorItem())

            self.toggle_menu_item = (
                AppKit.NSMenuItem.alloc()
                .initWithTitle_action_keyEquivalent_(
                    "Start Dictation",
                    "toggleDictation:",
                    "",
                )
            )
            self.toggle_menu_item.setTarget_(self)
            self.toggle_menu_item.setEnabled_(False)
            menu.addItem_(self.toggle_menu_item)

            settings_item = (
                AppKit.NSMenuItem.alloc()
                .initWithTitle_action_keyEquivalent_("Settings…", "showSettings:", ",")
            )
            settings_item.setTarget_(self)
            menu.addItem_(settings_item)
            menu.addItem_(AppKit.NSMenuItem.separatorItem())

            quit_item = (
                AppKit.NSMenuItem.alloc()
                .initWithTitle_action_keyEquivalent_("Quit", "quit:", "q")
            )
            quit_item.setTarget_(self)
            menu.addItem_(quit_item)
            self.status_item.setMenu_(menu)

        @objc.python_method
        def _build_window(self) -> None:
            frame = Foundation.NSMakeRect(0, 0, 480, 330)
            self.window = (
                AppKit.NSWindow.alloc()
                .initWithContentRect_styleMask_backing_defer_(
                    frame,
                    AppKit.NSWindowStyleMaskTitled
                    | AppKit.NSWindowStyleMaskClosable
                    | AppKit.NSWindowStyleMaskMiniaturizable
                    | AppKit.NSWindowStyleMaskFullSizeContentView,
                    AppKit.NSBackingStoreBuffered,
                    False,
                )
            )
            self.window.setTitle_("STT Settings")
            self.window.setTitleVisibility_(AppKit.NSWindowTitleHidden)
            self.window.setTitlebarAppearsTransparent_(True)
            self.window.setMovableByWindowBackground_(True)
            self.window.setReleasedWhenClosed_(False)
            self.window.setDelegate_(self)
            self.window.center()
            minimize_button = self.window.standardWindowButton_(
                AppKit.NSWindowMiniaturizeButton
            )
            minimize_button.setTarget_(self)
            minimize_button.setAction_("hideSettings:")

            background = AppKit.NSVisualEffectView.alloc().initWithFrame_(frame)
            background.setMaterial_(AppKit.NSVisualEffectMaterialUnderWindowBackground)
            background.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
            background.setState_(AppKit.NSVisualEffectStateActive)
            self.window.setContentView_(background)

            title = self._label(
                "STT",
                Foundation.NSMakeRect(24, 264, 250, 28),
                22,
                AppKit.NSFontWeightSemibold,
            )
            background.addSubview_(title)
            subtitle = self._label(
                "Private dictation, directly on your Mac.",
                Foundation.NSMakeRect(24, 240, 360, 18),
                13,
                AppKit.NSFontWeightRegular,
                secondary=True,
            )
            background.addSubview_(subtitle)

            self.tab_control = (
                AppKit.NSSegmentedControl.alloc()
                .initWithFrame_(Foundation.NSMakeRect(24, 198, 168, 26))
            )
            self.tab_control.setSegmentCount_(2)
            self.tab_control.setLabel_forSegment_("General", 0)
            self.tab_control.setLabel_forSegment_("Terms", 1)
            self.tab_control.setTrackingMode_(
                AppKit.NSSegmentSwitchTrackingSelectOne
            )
            self.tab_control.setSelectedSegment_(0)
            self.tab_control.setTarget_(self)
            self.tab_control.setAction_("tabChanged:")
            background.addSubview_(self.tab_control)

            self.general_view = AppKit.NSView.alloc().initWithFrame_(
                Foundation.NSMakeRect(0, 0, 480, 184)
            )
            self.terms_view = AppKit.NSView.alloc().initWithFrame_(
                Foundation.NSMakeRect(0, 0, 480, 184)
            )
            self.terms_view.setHidden_(True)
            background.addSubview_(self.general_view)
            background.addSubview_(self.terms_view)
            self._build_general_view()
            self._build_terms_view()
            self._update_mode_help()

        @objc.python_method
        def _build_general_view(self) -> None:
            self.status_dot = AppKit.NSView.alloc().initWithFrame_(
                Foundation.NSMakeRect(27, 154, 8, 8)
            )
            self.status_dot.setWantsLayer_(True)
            self.status_dot.layer().setCornerRadius_(4)
            self.general_view.addSubview_(self.status_dot)
            self.status_label = self._label(
                "Initializing…",
                Foundation.NSMakeRect(43, 146, 240, 20),
                13,
                AppKit.NSFontWeightMedium,
            )
            self.general_view.addSubview_(self.status_label)

            permissions = AppKit.NSButton.alloc().initWithFrame_(
                Foundation.NSMakeRect(352, 142, 104, 28)
            )
            permissions.setTitle_("Permissions…")
            permissions.setBezelStyle_(AppKit.NSBezelStyleRounded)
            permissions.setControlSize_(AppKit.NSControlSizeSmall)
            permissions.setTarget_(self)
            permissions.setAction_("openPermissions:")
            self.general_view.addSubview_(permissions)

            self.general_view.addSubview_(
                self._separator(Foundation.NSMakeRect(24, 128, 432, 1))
            )
            self.general_view.addSubview_(
                self._label(
                    "Shortcut",
                    Foundation.NSMakeRect(24, 92, 160, 20),
                    13,
                    AppKit.NSFontWeightMedium,
                )
            )
            self.shortcut_button = (
                AppKit.NSButton.alloc()
                .initWithFrame_(Foundation.NSMakeRect(320, 88, 136, 28))
            )
            self.shortcut_button.setTitle_(self.settings.hotkey.label)
            self.shortcut_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
            self.shortcut_button.setTarget_(self)
            self.shortcut_button.setAction_("recordShortcut:")
            self.general_view.addSubview_(self.shortcut_button)

            self.shortcut_cancel_button = (
                AppKit.NSButton.alloc()
                .initWithFrame_(Foundation.NSMakeRect(400, 88, 28, 28))
            )
            symbol_configuration = (
                AppKit.NSImageSymbolConfiguration
                .configurationWithPointSize_weight_(
                    12,
                    AppKit.NSFontWeightMedium,
                )
            )
            cancel_image = (
                AppKit.NSImage
                .imageWithSystemSymbolName_accessibilityDescription_(
                    "xmark",
                    "Cancel",
                )
                .imageWithSymbolConfiguration_(symbol_configuration)
            )
            self.shortcut_cancel_button.setImage_(cancel_image)
            self.shortcut_cancel_button.setImagePosition_(AppKit.NSImageOnly)
            self.shortcut_cancel_button.setToolTip_("Cancel")
            self.shortcut_cancel_button.setBezelStyle_(
                AppKit.NSBezelStyleCircular
            )
            self.shortcut_cancel_button.setTarget_(self)
            self.shortcut_cancel_button.setAction_("cancelShortcut:")
            self.shortcut_cancel_button.setHidden_(True)
            self.general_view.addSubview_(self.shortcut_cancel_button)

            self.shortcut_confirm_button = (
                AppKit.NSButton.alloc()
                .initWithFrame_(Foundation.NSMakeRect(432, 88, 28, 28))
            )
            confirm_image = (
                AppKit.NSImage
                .imageWithSystemSymbolName_accessibilityDescription_(
                    "checkmark",
                    "Save shortcut",
                )
                .imageWithSymbolConfiguration_(symbol_configuration)
            )
            self.shortcut_confirm_button.setImage_(confirm_image)
            self.shortcut_confirm_button.setImagePosition_(AppKit.NSImageOnly)
            self.shortcut_confirm_button.setToolTip_("Save shortcut")
            self.shortcut_confirm_button.setBezelStyle_(AppKit.NSBezelStyleCircular)
            self.shortcut_confirm_button.setTarget_(self)
            self.shortcut_confirm_button.setAction_("confirmShortcut:")
            self.shortcut_confirm_button.setHidden_(True)
            self.general_view.addSubview_(self.shortcut_confirm_button)

            self.general_view.addSubview_(
                self._label(
                    "Activation",
                    Foundation.NSMakeRect(24, 51, 160, 20),
                    13,
                    AppKit.NSFontWeightMedium,
                )
            )
            self.mode_control = (
                AppKit.NSSegmentedControl.alloc()
                .initWithFrame_(Foundation.NSMakeRect(280, 47, 176, 28))
            )
            self.mode_control.setSegmentCount_(2)
            self.mode_control.setLabel_forSegment_("Toggle", 0)
            self.mode_control.setLabel_forSegment_("Hold to Talk", 1)
            self.mode_control.setTrackingMode_(
                AppKit.NSSegmentSwitchTrackingSelectOne
            )
            self.mode_control.setSelectedSegment_(
                0
                if self.settings.activation_mode == ActivationMode.TOGGLE
                else 1
            )
            self.mode_control.setTarget_(self)
            self.mode_control.setAction_("modeChanged:")
            self.general_view.addSubview_(self.mode_control)

            self.mode_help = self._label(
                "",
                Foundation.NSMakeRect(24, 18, 432, 18),
                12,
                AppKit.NSFontWeightRegular,
                secondary=True,
            )
            self.general_view.addSubview_(self.mode_help)

        @objc.python_method
        def _build_terms_view(self) -> None:
            self.terms_view.addSubview_(
                self._label(
                    "Custom terms",
                    Foundation.NSMakeRect(24, 146, 220, 20),
                    13,
                    AppKit.NSFontWeightMedium,
                )
            )
            self.terms_view.addSubview_(
                self._label(
                    "Add names or uncommon words to improve recognition.",
                    Foundation.NSMakeRect(24, 123, 430, 18),
                    12,
                    AppKit.NSFontWeightRegular,
                    secondary=True,
                )
            )
            input_background = AppKit.NSView.alloc().initWithFrame_(
                Foundation.NSMakeRect(24, 78, 344, 32)
            )
            input_background.setWantsLayer_(True)
            input_background.layer().setCornerRadius_(7)
            input_background.layer().setBackgroundColor_(
                AppKit.NSColor.controlBackgroundColor().CGColor()
            )
            self.terms_view.addSubview_(input_background)

            self.terms_input = AppKit.NSTextField.alloc().initWithFrame_(
                Foundation.NSMakeRect(10, 5, 324, 22)
            )
            self.terms_input.setPlaceholderString_("Type a term and press Enter")
            self.terms_input.setBezeled_(False)
            self.terms_input.setDrawsBackground_(False)
            self.terms_input.setFocusRingType_(AppKit.NSFocusRingTypeNone)
            self.terms_input.setTarget_(self)
            self.terms_input.setAction_("addTerm:")
            input_background.addSubview_(self.terms_input)

            add_button = AppKit.NSButton.alloc().initWithFrame_(
                Foundation.NSMakeRect(376, 80, 80, 28)
            )
            add_button.setTitle_("Add")
            add_button.setBezelStyle_(AppKit.NSBezelStyleRounded)
            add_button.setTarget_(self)
            add_button.setAction_("addTerm:")
            self.terms_view.addSubview_(add_button)

            scroll_view = AppKit.NSScrollView.alloc().initWithFrame_(
                Foundation.NSMakeRect(24, 8, 432, 58)
            )
            scroll_view.setDrawsBackground_(False)
            scroll_view.setBorderType_(AppKit.NSNoBorder)
            scroll_view.setHasVerticalScroller_(True)
            scroll_view.setAutohidesScrollers_(True)
            self.terms_chip_view = FlippedView.alloc().initWithFrame_(
                Foundation.NSMakeRect(0, 0, 414, 58)
            )
            scroll_view.setDocumentView_(self.terms_chip_view)
            self.terms_view.addSubview_(scroll_view)
            self._refresh_terms()

        @objc.python_method
        def _install_shortcut_capture(self) -> None:
            event_mask = (
                AppKit.NSEventMaskKeyDown
                | AppKit.NSEventMaskFlagsChanged
            )

            def handle(event: Any) -> Any:
                if not self.is_capturing:
                    return event

                key_code = int(event.keyCode())
                modifiers = int(event.modifierFlags()) & MODIFIER_MASK
                event_type = int(event.type())

                if event_type == AppKit.NSEventTypeFlagsChanged:
                    modifier = MODIFIER_KEY_CODES.get(key_code)
                    if modifier not in DOUBLE_TAP_MODIFIERS:
                        return None
                    if modifiers & modifier:
                        other_modifiers = modifiers & (
                            MODIFIER_MASK & ~modifier
                        )
                        if other_modifiers:
                            self.capture_chorded_modifiers |= (
                                modifier | other_modifiers
                            )
                        return None
                    if self.capture_chorded_modifiers & modifier:
                        self.capture_chorded_modifiers &= ~modifier
                        self.capture_pending_tap = None
                        self.capture_pending_tap_at = 0.0
                        return None

                    self._capture_tap(
                        HotkeyBinding.double_modifier(modifier),
                        float(event.timestamp()),
                    )
                    return None

                if bool(event.isARepeat()):
                    return None
                if not modifiers:
                    self._capture_tap(
                        HotkeyBinding.double_key(key_code),
                        float(event.timestamp()),
                    )
                    return None

                self.capture_chorded_modifiers = modifiers
                self.capture_pending_tap = None
                self.capture_pending_tap_at = 0.0
                self._show_shortcut_candidate(
                    HotkeyBinding.key_combination(key_code, modifiers)
                )
                return None

            self.event_monitor = (
                AppKit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                    event_mask,
                    handle,
                )
            )

        @objc.python_method
        def _capture_tap(
            self,
            hotkey: HotkeyBinding,
            timestamp: float,
        ) -> None:
            if (
                hotkey == self.capture_pending_tap
                and timestamp - self.capture_pending_tap_at <= 0.45
            ):
                self.capture_pending_tap = None
                self.capture_pending_tap_at = 0.0
                self._show_shortcut_candidate(hotkey)
            else:
                self.capture_pending_tap = hotkey
                self.capture_pending_tap_at = timestamp

        @objc.python_method
        def _show_shortcut_candidate(self, hotkey: HotkeyBinding) -> None:
            self.shortcut_candidate = hotkey
            self.shortcut_button.setTitle_(hotkey.label)
            self.shortcut_confirm_button.setEnabled_(True)
            self.mode_help.setStringValue_("")

        @objc.python_method
        def _finish_capture(self, *, save: bool = False) -> None:
            self.is_capturing = False
            self.shortcut_button.setFrame_(
                Foundation.NSMakeRect(320, 88, 136, 28)
            )
            self.shortcut_cancel_button.setHidden_(True)
            self.shortcut_confirm_button.setHidden_(True)
            self.shortcut_candidate = None
            self.capture_pending_tap = None
            self.capture_pending_tap_at = 0.0
            self.capture_chorded_modifiers = 0
            if save:
                self._persist_settings()
            else:
                self.shortcut_button.setTitle_(self.settings.hotkey.label)
                self._update_mode_help()
                if self.engine is not None:
                    self.engine.apply(self.settings)

        @objc.python_method
        def _persist_settings(self) -> None:
            self.settings = self.settings.normalized()
            save_settings(self.settings)
            self.shortcut_button.setTitle_(self.settings.hotkey.label)
            self.mode_control.setSelectedSegment_(
                0
                if self.settings.activation_mode == ActivationMode.TOGGLE
                else 1
            )
            self._update_mode_help()
            if self.engine is not None:
                self.engine.apply(self.settings)

        @objc.python_method
        def _update_mode_help(self) -> None:
            text = (
                "Press the shortcut once to start and again to stop."
                if self.settings.activation_mode == ActivationMode.TOGGLE
                else "Dictation runs only while the shortcut is held."
            )
            self.mode_help.setStringValue_(text)

        @objc.python_method
        def _receive_status(self, status: str, detail: str | None) -> None:
            def update() -> None:
                self._set_status(status, detail)

            Foundation.NSOperationQueue.mainQueue().addOperationWithBlock_(update)

        @objc.python_method
        def _set_status(self, status: str, detail: str | None) -> None:
            states = {
                "initializing": ("Initializing…", False),
                "ready": ("Ready", True),
                "listening": ("Listening…", True),
                "processing": ("Processing…", False),
                "paused": ("Shortcut paused", False),
                "stopped": ("Stopped", False),
                "error": (detail or "STT needs attention", False),
            }
            label, can_toggle = states.get(
                status,
                ("Working…", False),
            )
            permission_panes = {
                "Accessibility required": "Privacy_Accessibility",
            }
            self.needs_permission_retry = (
                status == "error" and detail in permission_panes
            )
            if detail in permission_panes:
                self.permission_pane = permission_panes[detail]
            self.status_label.setStringValue_(label)
            self.status_menu_item.setTitle_(label)
            colors = {
                "initializing": AppKit.NSColor.systemTealColor(),
                "ready": AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(
                    0.38,
                    0.76,
                    0.90,
                    1.0,
                ),
                "listening": AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(
                    0.43,
                    0.82,
                    0.56,
                    1.0,
                ),
                "processing": AppKit.NSColor.systemOrangeColor(),
                "error": AppKit.NSColor.systemRedColor(),
            }
            self.status_dot.layer().setBackgroundColor_(
                colors.get(
                    status,
                    AppKit.NSColor.secondaryLabelColor(),
                ).CGColor()
            )
            self.toggle_menu_item.setEnabled_(can_toggle)
            self.toggle_menu_item.setTitle_(
                "Stop & Transcribe" if status == "listening" else "Start Dictation"
            )

        @objc.python_method
        def _refresh_terms(self) -> None:
            for view in list(self.terms_chip_view.subviews()):
                view.removeFromSuperview()

            x = 0
            y = 0
            for index, term in enumerate(self.terms):
                title = (
                    Foundation.NSMutableAttributedString.alloc()
                    .initWithString_attributes_(
                        term,
                        {
                            AppKit.NSFontAttributeName: (
                                AppKit.NSFont.systemFontOfSize_weight_(
                                    11,
                                    AppKit.NSFontWeightRegular,
                                )
                            ),
                            AppKit.NSForegroundColorAttributeName: (
                                AppKit.NSColor.labelColor()
                            ),
                        },
                    )
                )
                title.appendAttributedString_(
                    Foundation.NSAttributedString.alloc()
                    .initWithString_attributes_(
                        "   ×",
                        {
                            AppKit.NSFontAttributeName: (
                                AppKit.NSFont.systemFontOfSize_weight_(
                                    10,
                                    AppKit.NSFontWeightRegular,
                                )
                            ),
                            AppKit.NSForegroundColorAttributeName: (
                                AppKit.NSColor.secondaryLabelColor()
                            ),
                            AppKit.NSBaselineOffsetAttributeName: 1,
                        },
                    )
                )
                chip = AppKit.NSButton.alloc().init()
                chip.setAttributedTitle_(title)
                chip.setBordered_(False)
                chip.setWantsLayer_(True)
                chip.layer().setCornerRadius_(6)
                chip.layer().setBackgroundColor_(
                    AppKit.NSColor.quaternaryLabelColor().CGColor()
                )
                chip.setTarget_(self)
                chip.setAction_("removeTerm:")
                chip.setTag_(index)
                width = min(220, max(44, title.size().width + 20))
                if x and x + width > 414:
                    x = 0
                    y += 28

                chip.setFrame_(Foundation.NSMakeRect(x, y, width, 22))
                self.terms_chip_view.addSubview_(chip)
                x += width + 8

            height = max(58, y + 24)
            self.terms_chip_view.setFrameSize_(
                Foundation.NSMakeSize(414, height)
            )

        @objc.python_method
        def _label(
            self,
            text: str,
            frame: Any,
            size: float,
            weight: float,
            *,
            secondary: bool = False,
        ) -> Any:
            label = AppKit.NSTextField.labelWithString_(text)
            label.setFrame_(frame)
            label.setFont_(AppKit.NSFont.systemFontOfSize_weight_(size, weight))
            label.setTextColor_(
                AppKit.NSColor.secondaryLabelColor()
                if secondary
                else AppKit.NSColor.labelColor()
            )
            return label

        @objc.python_method
        def _separator(self, frame: Any) -> Any:
            separator = AppKit.NSBox.alloc().initWithFrame_(frame)
            separator.setBoxType_(AppKit.NSBoxSeparator)
            return separator

    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()


if __name__ == "__main__":
    run()
