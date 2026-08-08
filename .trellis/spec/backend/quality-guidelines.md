# Quality Guidelines

> Code quality standards for backend development.

---

## Scenario: Recorded, Replayed, and Guarded Game Automation

### 1. Scope / Trigger

This contract applies whenever code captures game input, replays a fixture, or sends
mouse/keyboard input to a real game window. It prevents production paths from bypassing
mock replay, observe-only mode, action limits, or emergency stop.

### 2. Signatures

- `GameEnvironment.left_click(x: int, y: int) -> None`
- `GameEnvironment.key_press(key_code: int) -> None`
- `GuardedEnvironment(delegate, guard, observe_only=True)`
- `RunGuard(timeout_seconds=180.0, max_actions=30, unknown_limit=3)`
- `python tools/record_gameplay.py record --scenario <id>`
- `WindowsEnvironment(hwnd=None, window_title="阴阳师", capture_mode="print_window")`
- `WindowsEnvironment.activate_window() -> None`
- `RecordingSession._validate_first_frame(frame: np.ndarray) -> None`
- `RecordingSession._create_video_writer(path, codec, fps, size)`
- `python tools/build_replay_fixture.py candidates <recording> --output <json>`
- `python tools/build_replay_fixture.py build <recording> <confirmation> <output>`
- `build_confirmed_fixture(recording_dir: Path, confirmation_path: Path, output_dir: Path) -> Path`
- `python tools/run_guarded_script.py realm_raid [--execute]`
- `python tools/run_guarded_script.py realm_raid [--execute] [--confirmation-phrase <exact>]`
- `RealmRaidScript._on_battling(point: tuple[int, int]) -> None`
- `RunGuard.allow_unknown_for(seconds: float) -> None`

### 3. Contracts

- Coordinates persisted by the recorder are client-relative; desktop absolute coordinates
  are forbidden.
- Raw recordings stay under ignored `recordings/`; only user-confirmed minimal fixtures
  may enter Git.
- A confirmation may define top-level `scenes` independently from `transitions`.
  Each scene selects either `event_seq` plus `frame_phase` (`before` or `after`), or a
  relative `source_path` contained by the recording directory. Transitions may reference
  only scenes already confirmed in that list.
- Fixture scene paths are serialized with POSIX separators so the same tracked JSON is
  stable on Windows and non-Windows hosts.
- Production image templates that participate in a recorded flow must be exercised
  against a sanitized real fixture. A unit test with a mocked match result is not enough
  to detect live UI drift.
- Unit-test modules collected in the same pytest process as recorded-replay tests must
  not replace `cv2`, `numpy`, or the root `PIL` package in `sys.modules`. Mock only the
  OS-facing leaf dependencies needed by that test; otherwise later replay collection
  silently runs production template matching against `MagicMock` objects.
- An image-search rectangle must fully contain the template at every valid match
  position. The right/bottom search boundary cannot cut through the template.
- Realm-raid automatic group change requires both a victory-count increase since the
  current round started and a real match for `realm_raid_record_zero.bmp`. Either signal
  alone is insufficient.
- A settlement image that is also reused by realm-raid milestone rewards must not be
  treated as proof of a battle by itself. Arm settlement counting from a confirmed attack
  or persistent battle marker, consume the arm on the first matching settlement, and still
  dismiss an unarmed reward dialog without increasing the battle count.
- Every long-lived runtime state must own at least one registered image event. A real
  frame is considered known by `RunGuard` only when `_trigger_event_from_screenshot_cache`
  returns a registered event; adding a fixture scene or a `SceneManager` template alone
  does not satisfy this contract.
- A battle-running marker callback must be input-free unless the business flow explicitly
  requires an action. Its purpose is to reset the unknown-frame counter while waiting for
  an independently registered battle-end event.
- A persistent battle marker may refresh a short trailing unknown-frame grace period on
  every match. This bridges the deterministic interval after the marker disappears and
  before a settlement template appears. The callback must remain input-free, and the
  grace must not bypass timeout, action budget, or emergency stop.
- A long-lived state marker must remain visible through the early, middle, and late parts
  of that state. Auto-hiding entrance panels, buff banners, and tutorial overlays are not
  valid state markers even if one confirmed frame matches them. When a recording is
  available, measure timeline coverage and also reject the following state as a negative
  fixture.
- A deterministic transition may request a short unknown-frame grace period only after a
  confirmed business action. Grace suppresses unknown counting, not timeout, action limit,
  or emergency stop. When grace is armed inside a recognized event callback, that event's
  later `note_iteration(True)` receipt preserves grace; the next recognized event ends it.
- On Windows, video creation must try `cv2.CAP_MSMF` before OpenCV's default backend.
  Some project environments report GStreamer as enabled while its plugin DLL
  dependencies are incomplete.
- If MSMF cannot open the requested codec, release that writer before falling back to
  OpenCV's default backend. The session's existing `isOpened()` check remains the final
  failure boundary.
- After releasing a Windows video writer, finalizing the recording directory may briefly
  raise `PermissionError` while the OS closes the MP4 handle. Retry the rename within a
  bounded window, and preserve the `.partial` directory if all attempts fail.
- `WindowsEnvironment` defaults to `capture_mode="print_window"` so ordinary background
  automation retains its existing behavior. The interactive recorder and guarded
  `--execute` path select `capture_mode="foreground"` because hardware-accelerated battle
  rendering is not semantically reliable through `PrintWindow`.
- After terminal confirmation, the recorder and guarded execute path restore and activate
  the target window, wait briefly for composition, and only then capture the first frame.
- Guarded observe mode remains on `print_window` and never activates the target window.
  Observation must not steal focus or send input.
- Foreground capture converts both client-rectangle corners with `ClientToScreen`, uses
  `ImageGrab.grab(..., all_screens=True)`, and refuses to capture unless the target
  window is the foreground window.
- A first frame with no pixels or standard deviation below `1.0` is invalid. Reject it
  before constructing a video writer or starting the input monitor.
- All runtime input must pass through the injected `GameEnvironment`, including scene
  navigation and `ESC`/`ENTER`.
- Observe-only mode records planned logical actions and sends no input to the delegate.
- Real execution requires the exact mode-and-script confirmation phrase. The default path
  reads it from an interactive terminal. While a user has explicitly authorized the
  active task to self-debug, `--confirmation-phrase` may supply the same exact phrase to
  one non-interactive process. This is not a generic `--yes` bypass.
- One run never starts another run automatically.

### 4. Validation & Error Matrix

| Condition | Required result |
|---|---|
| Unknown recording or fixture schema version | Raise `ValueError` at the shared decoder |
| Client coordinate outside the recorded window | Raise `ValueError` |
| Window size changes during recording | Stop and preserve failed metadata |
| Foreground capture target is not the active window | Raise `RuntimeError`; never capture unrelated desktop content |
| First frame is empty or has standard deviation below `1.0` | Preserve failed metadata and abort before video/input startup |
| Unknown `capture_mode` | Raise `ValueError` during environment construction |
| Guarded `--execute` starts after exact confirmation | Construct `foreground` capture, activate the game, then start recognition |
| Guarded observe mode starts | Construct `print_window` capture and do not activate the game |
| Confirmed scene uses an unknown `frame_phase` | Raise `ValueError`; allow only `before` or `after` |
| Confirmed `source_path` escapes the recording directory | Raise `ValueError`; copy nothing |
| Transition references a scene absent from confirmed `scenes` | Raise `ValueError` |
| A unit-test module runs before a real-image replay module | Real `cv2`, `numpy`, and `PIL` remain importable; template matching produces the same result as an isolated replay run |
| Search rectangle is narrower or shorter than its template placement | Fix the bounds and add a real-fixture regression |
| Realm-raid record is zero but no victory was gained this round | Keep the current round; this can be the quit-three sequence |
| Victory increased but record-zero template is absent | Keep the current round and wait for reliable visual evidence |
| Realm-raid settlement image appears without an armed attack/battle state | Dismiss the reward dialog, keep the battle count unchanged, and continue scene detection |
| Battle frame matches no registered image event | Count as unknown and stop at `unknown_limit`; add a confirmed state marker rather than increasing the limit |
| Battle-running marker matches | Return a known event, reset the unknown counter, and send no input |
| Battle marker disappears before a settlement template appears | Keep unknown count at zero only for the marker-refreshed trailing grace; recognize settlement normally when it appears |
| Candidate marker matches only an entrance panel or a short prefix of a long-lived state | Reject it; select a persistent control and verify early/middle/late coverage |
| Candidate battle-running marker also matches the recorded battle summary | Reject it; the passive running event must not mask battle-end handling |
| Unknown frame occurs inside an action-scoped grace period | Keep `consecutive_unknown=0`; continue checking all other fuses |
| The same recognized event that armed grace reaches `note_iteration(True)` | Reset unknown count but preserve grace for the following transition |
| A later event is recognized during grace | Reset unknown count and terminate grace immediately |
| Grace seconds are zero or negative | Raise `ValueError` |
| MSMF opens the MP4 writer | Use it without probing GStreamer |
| MSMF cannot open the MP4 writer | Release it, try the default backend once, then fail through `isOpened()` |
| Windows directory finalization gets a transient `PermissionError` | Retry the rename for a bounded interval; preserve `.partial` if the final attempt fails |
| Action number would exceed `max_actions` | Block the action and set `action_limit` |
| Runtime reaches `timeout_seconds` | Set `timeout` and stop the event loop |
| Consecutive unknown frames reach `unknown_limit` | Set `unknown_scene` and stop |
| F12 is pressed | Set `emergency_stop`; later reasons must not overwrite it |
| Non-interactive real-run request without `--confirmation-phrase` | Return exit code `2` before resolving a window |
| Supplied confirmation phrase differs from the exact mode-and-script phrase | Return exit code `1` before resolving a window |
| User-authorized non-interactive run supplies the exact phrase | Start one guarded process with the same capture and fuse configuration as the interactive path |
| Retry or refresh confirmation is missing | Stop the business flow; do not guess-click |

### 5. Good / Base / Bad Cases

- Good: a `SceneManager` click calls `self.win_controller.mouse`, so injected guards and
  replay environments observe it.
- Good: Windows MP4 creation explicitly passes `cv2.CAP_MSMF`.
- Good: recording finalization retries transient Windows MP4-handle `PermissionError` and
  still exposes `.partial` evidence after the bounded retry window.
- Good: the recorder activates the game, captures its visible client rectangle, and
  validates visual variance before listening for input.
- Good: guarded execute uses foreground capture after confirmation, while guarded observe
  keeps `PrintWindow` and does not change focus.
- Good: a scene that exists only after a later event uses an explicit
  `{"event_seq": 17, "frame_phase": "after"}` confirmation.
- Good: a logic-only test mocks `PIL.ImageGrab` and Win32 modules while leaving the root
  image-processing packages real for replay tests collected later.
- Good: the production `SceneManager` is run from a sanitized recorded home frame through
  the real exploration and realm-raid templates.
- Good: realm raid registers the persistent bottom-left “自动” control with a no-op
  callback, matches complete recorded battle intervals, and does not match the recorded
  post-battle summary; victory/loss templates remain responsible for settlement actions.
- Good: clicking a confirmed attack button grants 12 seconds for loading/entry animation;
  the battle marker cancels the remaining grace as soon as it appears.
- Good: each persistent battle-marker match refreshes a five-second, input-free trailing
  grace; the victory template appears during that interval and ends grace normally.
- Good: realm raid consumes one armed settlement on the first matching reward image;
  the same image used by a 3/6/9-grid milestone reward is dismissed without a second
  battle count.
- Good: an explicitly authorized debugging process passes
  `--confirmation-phrase "RUN realm_raid"` and still uses foreground capture, action
  limits, timeout, unknown limits, F12, and one-process-one-run behavior.
- Base: ordinary scripts without an injected environment keep the legacy Win32 behavior.
- Base: background automation continues to use `PrintWindow`; foreground capture is an
  explicit recorder-only choice.
- Base: non-Windows environments retain OpenCV's default backend selection.
- Bad: a script imports and calls `bg_left_click_with_range(hwnd, ...)` directly. This
  bypasses the injected environment and invalidates safety limits.
- Bad: Windows MP4 creation uses the four-argument `cv2.VideoWriter(...)` overload first;
  it can select a broken GStreamer installation even when MSMF works.
- Bad: treating a successful `PrintWindow` return value as proof that the game content
  was captured. Hardware-accelerated windows may return a uniform white image.
- Bad: because `PrintWindow` captures a static grid or reward screen correctly, assuming
  it also captures the hardware-accelerated battle phase correctly.
- Bad: forcing every scene to come from the same event as a transition. Recorded state
  machines often need a stable frame from a later event.
- Bad: assigning `MagicMock()` to `sys.modules["cv2"]`, `sys.modules["numpy"]`, or
  `sys.modules["PIL"]` at test-module import time. The assignment outlives that module
  and makes replay results depend on pytest collection order.
- Bad: cropping a template through `x=245` and searching only through `x1=230`; template
  matching cannot place an image outside the supplied search buffer.
- Bad: treating “攻略记录 0” alone as a new realm-raid group. The first target's
  quit-three sequence also occurs while the record is zero.
- Bad: incrementing the realm-raid battle counter whenever `battle_end_1.bmp` matches;
  milestone rewards and a repeated settlement frame can use the same image.
- Bad: assuming that a scene present in a replay fixture is automatically known to the
  event loop. `SceneReplayEnvironment`, `SceneManager`, and registered image events are
  separate layers.
- Bad: raising `unknown_limit` to hide a deterministic, long-lived unregistered battle
  state. This weakens the safety fuse for genuinely unknown screens.
- Bad: using the auto-hiding “结界加成” panel as the only battle-running marker because it
  matches one early frame; after the panel closes, the guard sees the same battle as unknown.
- Bad: granting grace at process startup or after an unrecognized frame. Grace must be
  causally attached to an action whose expected transition is known.
- Bad: using a generic `--yes` flag or accepting a partial confirmation such as `RUN`;
  non-interactive authorization must carry the complete expected phrase.
- Bad: adding a click to a passive battle marker merely to keep the event loop alive.
- Bad: allowing grace to postpone total timeout or F12 emergency stop.

### 6. Tests Required

- Unit: observe mode records an action while the delegate action log remains empty.
- Unit: action, timeout, unknown-frame, and emergency-stop reasons are deterministic.
- Unit: keyboard and drag count as one logical action each.
- Integration: scene navigation through an injected environment is recorded.
- Integration: event loop stops after the configured unknown-frame limit.
- Regression: each new nine-grid can run the quit-three sequence once, never twice.
- Fixture builder: independently selected before/after scenes copy correctly, unsafe
  source paths fail, and JSON paths use `/`.
- Recorded replay: production scene templates navigate home → exploration →
  barrier-breakthrough at the normal similarity threshold.
- Test isolation: run logic-only tests before their related recorded-replay tests in one
  pytest invocation and assert the real template match still succeeds.
- Recorded replay: the record-zero template matches the sanitized new-grid frame inside
  the exact production search rectangle.
- Realm raid: record zero without a new victory does not reset a round; record zero plus
  a new victory resets before selecting the next target.
- Guarded real-frame regression: each long-lived state marker must be triggered through
  the production event loop, and its no-op callback must leave the action log empty.
- Marker persistence regression: verify representative early/middle/late recorded frames
  match the long-lived state marker, and verify the following summary/settlement frame
  does not match it.
- Guard unit: unknown frames inside grace do not accumulate; recognized events end grace;
  timeout remains effective; non-positive grace is rejected.
- Business integration: direct attack and successful quit-three completion request grace,
  while failed retry does not.
- Business integration: a real battle marker produces no input and refreshes a bounded
  settlement-transition grace; three unknown observations during that grace do not stop.
- Realm raid: a recorded milestone reward image is dismissed without incrementing the
  battle counter, while one armed battle settlement increments it exactly once.
- CLI: non-interactive startup without a phrase and any mismatched phrase fail before
  window construction; an exact authorized phrase reaches the same guarded execute
  orchestration without calling interactive input.
- Guarded CLI: execute constructs `foreground` capture and activates once; observe
  constructs `print_window` capture and never activates.
- Recorder: on Windows, assert the first writer call includes `cv2.CAP_MSMF`; if it is
  closed, assert it is released before one default-backend fallback call.
- Recorder: foreground capture must assert the exact desktop bounding box, foreground
  ownership, multi-monitor flag, and restore/focus calls.
- Recorder: a uniform first frame must fail before writer creation, retain failed
  metadata, and never start the input monitor.

### 7. Wrong vs Correct

#### Wrong

```python
from win_util.mouse import bg_left_click_with_range

bg_left_click_with_range(self.hwnd, button_pos)
```

#### Correct

```python
self.win_controller.mouse.bg_left_click_with_range(button_pos)
```

The correct form preserves production compatibility while allowing `MockEnvironment`,
`SceneReplayEnvironment`, and `GuardedEnvironment` to intercept the action.

#### Wrong (Windows video writer)

```python
cv2.VideoWriter(str(path), fourcc, fps, size)
```

#### Correct (Windows video writer)

```python
writer = cv2.VideoWriter(str(path), cv2.CAP_MSMF, fourcc, fps, size)
if not writer.isOpened():
    writer.release()
    writer = cv2.VideoWriter(str(path), fourcc, fps, size)
```

This avoids a broken GStreamer plugin chain when the same OpenCV build can write MP4
successfully through Windows Media Foundation.

#### Wrong (guarded hardware-accelerated execution)

```python
env = WindowsEnvironment(window_title="阴阳师")
run_guarded_execute(env)
```

#### Correct (guarded hardware-accelerated execution)

```python
env = WindowsEnvironment(
    window_title="阴阳师",
    capture_mode="foreground",
)
env.activate_window()
time.sleep(0.5)
run_guarded_execute(env)
```

Capture validity is a contract of the backend and rendering phase together. A static
screen match cannot validate a hardware-accelerated battle frame.

#### Wrong (game recording capture)

```python
rendered = PrintWindow(hwnd, target_dc, PW_CLIENTONLY)
if rendered:
    start_long_recording()
```

#### Correct (game recording capture)

```python
env = WindowsEnvironment(capture_mode="foreground")
env.activate_window()
frame = capture_client_rect_from_desktop(env.hwnd)
RecordingSession._validate_first_frame(frame)
```

An API success flag validates only the call, not the semantic content. Long-running
recording must start only after a real frame passes content-level validation.

#### Wrong (recorded scene selection)

```python
# 把转换事件的 before/after 强制当成全部场景来源
source = recording_dir / "frames" / f"{transition_seq:06d}-before.png"
```

#### Correct (recorded scene selection)

```python
source = _resolve_confirmed_frame(
    recording_dir,
    {"event_seq": scene_seq, "frame_phase": "after"},
)
```

Scene identity and transition identity are separate contracts. Explicit scene selection
keeps the fixture minimal while allowing stable frames from different moments.

#### Wrong (realm-raid automatic group change)

```python
if find_record_zero():
    self._start_new_round()
```

#### Correct (realm-raid automatic group change)

```python
if (
    self._cur_battle_victory_count > self.round_state.victory_count_at_start
    and find_record_zero()
):
    self._start_new_round()
```

The state signal and visual signal jointly distinguish an actual automatic group change
from the initial zero-record screen seen during the quit-three sequence.

#### Wrong (guarded battle recognition)

```python
# 回放夹具里有 battling 场景，所以误以为保险丝会自动识别
fixture.scenes["battling"] = "scenes/battling.png"
```

#### Correct (guarded battle recognition)

```python
self._register_image_match_event(
    ImageMatchConfig("yys/realm_raid/images/realm_raid_battling.bmp"),
    self._on_battling,
)

def _on_battling(self, _point: tuple[int, int]) -> None:
    """确认战斗仍在进行，不发送输入。"""
```

The event registration, not the fixture scene name, is what makes
`RunGuard.note_iteration(triggered_event is not None)` reset its unknown counter.

#### Wrong (long-lived battle marker)

```python
# “结界加成”只在入场后的短时间内可见
template = crop(early_battle_frame, temporary_buff_panel)
```

#### Correct (long-lived battle marker)

```python
# “自动”控件覆盖完整战斗，且战后总结画面中不存在
template = crop(confirmed_battle_frame, persistent_auto_control)
assert matches_early_middle_late_frames(template)
assert not matches_battle_summary(template)
```

A single positive screenshot proves only local recognizability. A long-lived runtime
state requires temporal coverage plus a negative assertion at the next state boundary.

#### Wrong (transition safety)

```python
# 全局放宽所有未知画面，掩盖真正异常
guard = RunGuard(unknown_limit=15)
```

#### Correct (transition safety)

```python
self.bg_left_click(attack_point)
guard.allow_unknown_for(12.0)
```

The correct form keeps the global three-frame fuse intact and scopes tolerance to a
confirmed action. The event-loop receipt for this attack event preserves the newly armed
grace; a later recognized battle or settlement event ends it. Timeout, action budget, and
emergency stop remain active throughout.

#### Wrong (battle-to-settlement transition)

```python
def _on_battling(self, _point: tuple[int, int]) -> None:
    pass
```

#### Correct (battle-to-settlement transition)

```python
def _on_battling(self, _point: tuple[int, int]) -> None:
    if self._run_guard is not None:
        self._run_guard.allow_unknown_for(
            self.BATTLE_SETTLEMENT_GRACE_SECONDS,
        )
```

The marker remains input-free. Refreshing a short grace while the marker is visible
covers only its deterministic trailing transition; the next victory or reward event
terminates grace and retains responsibility for all clicks and counters.

#### Wrong (authorized non-interactive execution)

```powershell
python tools/run_guarded_script.py realm_raid --execute --yes
```

#### Correct (authorized non-interactive execution)

```powershell
python tools/run_guarded_script.py realm_raid --execute `
  --confirmation-phrase "RUN realm_raid"
```

The exact phrase couples authorization to both mode and script. A missing or mismatched
phrase fails before the game window is resolved, and the process still executes only one
guarded run.
