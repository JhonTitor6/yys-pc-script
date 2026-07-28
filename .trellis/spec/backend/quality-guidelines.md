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
- An image-search rectangle must fully contain the template at every valid match
  position. The right/bottom search boundary cannot cut through the template.
- Realm-raid automatic group change requires both a victory-count increase since the
  current round started and a real match for `realm_raid_record_zero.bmp`. Either signal
  alone is insufficient.
- On Windows, video creation must try `cv2.CAP_MSMF` before OpenCV's default backend.
  Some project environments report GStreamer as enabled while its plugin DLL
  dependencies are incomplete.
- If MSMF cannot open the requested codec, release that writer before falling back to
  OpenCV's default backend. The session's existing `isOpened()` check remains the final
  failure boundary.
- `WindowsEnvironment` defaults to `capture_mode="print_window"` so ordinary background
  automation retains its existing behavior. The interactive recorder alone selects
  `capture_mode="foreground"`.
- After terminal confirmation, the recorder restores and activates the target window,
  waits briefly for composition, and only then captures the first frame.
- Foreground capture converts both client-rectangle corners with `ClientToScreen`, uses
  `ImageGrab.grab(..., all_screens=True)`, and refuses to capture unless the target
  window is the foreground window.
- A first frame with no pixels or standard deviation below `1.0` is invalid. Reject it
  before constructing a video writer or starting the input monitor.
- All runtime input must pass through the injected `GameEnvironment`, including scene
  navigation and `ESC`/`ENTER`.
- Observe-only mode records planned logical actions and sends no input to the delegate.
- Real execution requires an interactive terminal and the exact confirmation phrase.
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
| Confirmed scene uses an unknown `frame_phase` | Raise `ValueError`; allow only `before` or `after` |
| Confirmed `source_path` escapes the recording directory | Raise `ValueError`; copy nothing |
| Transition references a scene absent from confirmed `scenes` | Raise `ValueError` |
| Search rectangle is narrower or shorter than its template placement | Fix the bounds and add a real-fixture regression |
| Realm-raid record is zero but no victory was gained this round | Keep the current round; this can be the quit-three sequence |
| Victory increased but record-zero template is absent | Keep the current round and wait for reliable visual evidence |
| MSMF opens the MP4 writer | Use it without probing GStreamer |
| MSMF cannot open the MP4 writer | Release it, try the default backend once, then fail through `isOpened()` |
| Action number would exceed `max_actions` | Block the action and set `action_limit` |
| Runtime reaches `timeout_seconds` | Set `timeout` and stop the event loop |
| Consecutive unknown frames reach `unknown_limit` | Set `unknown_scene` and stop |
| F12 is pressed | Set `emergency_stop`; later reasons must not overwrite it |
| Non-interactive real-run request | Return exit code `2` before resolving a window |
| Retry or refresh confirmation is missing | Stop the business flow; do not guess-click |

### 5. Good / Base / Bad Cases

- Good: a `SceneManager` click calls `self.win_controller.mouse`, so injected guards and
  replay environments observe it.
- Good: Windows MP4 creation explicitly passes `cv2.CAP_MSMF`.
- Good: the recorder activates the game, captures its visible client rectangle, and
  validates visual variance before listening for input.
- Good: a scene that exists only after a later event uses an explicit
  `{"event_seq": 17, "frame_phase": "after"}` confirmation.
- Good: the production `SceneManager` is run from a sanitized recorded home frame through
  the real exploration and realm-raid templates.
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
- Bad: forcing every scene to come from the same event as a transition. Recorded state
  machines often need a stable frame from a later event.
- Bad: cropping a template through `x=245` and searching only through `x1=230`; template
  matching cannot place an image outside the supplied search buffer.
- Bad: treating “攻略记录 0” alone as a new realm-raid group. The first target's
  quit-three sequence also occurs while the record is zero.

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
- Recorded replay: the record-zero template matches the sanitized new-grid frame inside
  the exact production search rectangle.
- Realm raid: record zero without a new victory does not reset a round; record zero plus
  a new victory resets before selecting the next target.
- CLI: non-interactive startup and a mismatched confirmation phrase fail before window
  construction.
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
