extends Node3D
# pet.gd — Full-body VRM avatar driver for the Zendaya state server.
#
# Polls GET /ai_status 4Hz and maps state (idle / thinking / talking) into:
#   • Procedural skeletal animation (head, neck, chest, spine, arms, hips)
#   • Breathing rise/fall on the chest + spine
#   • Eye saccades (the avatar's gaze drifts naturally, not a stare)
#   • Blend shapes for facial expressions and a sine-wave lipsync
# POSTs chat input back to the server so you can talk via the desktop pet.

const STATUS_URL := "http://127.0.0.1:7475/ai_status"
const CHAT_URL   := "http://127.0.0.1:7475/chat"
const WINDOW_URL := "http://127.0.0.1:7475/window"
const WINDOW_CONTROL_URL := "http://127.0.0.1:7475/window/control"
const SELF_TITLE := "Zendaya Pet"

# Toggle to disable perch-on-window behaviour entirely.
const auto_follow := true
# Seconds of pure idle on the same window before she falls asleep.
const SLEEP_AFTER := 8.0
# Pixel radius at which "walking" snaps into "perched".
const ARRIVE_RADIUS := 30.0

enum BehaviourState { IDLE_FREESTAND, WALK, PERCH, SLEEP }

@onready var avatar_root: Marker3D     = $Avatar
@onready var status_poll: HTTPRequest  = $StatusPoll
@onready var chat_post:   HTTPRequest  = $ChatPost
@onready var poll_timer:  Timer        = $PollTimer
@onready var reply_label: Label        = $UI/Root/ReplyLabel
@onready var chat_input:  LineEdit     = $UI/Root/ChatInput
@onready var window_poll: HTTPRequest  = $WindowPoll
@onready var window_control_post: HTTPRequest = $WindowControlPost
@onready var window_timer: Timer       = $WindowTimer

# Avatar handles
var avatar_node: Node = null
var skeleton: Skeleton3D = null
var blend_meshes: Array[MeshInstance3D] = []

# Bone indices (-1 = absent on this rig)
var bone_head := -1
var bone_neck := -1
var bone_chest := -1
var bone_upper_chest := -1
var bone_spine := -1
var bone_hips := -1
var bone_l_shoulder := -1
var bone_r_shoulder := -1
var bone_l_upper_arm := -1
var bone_r_upper_arm := -1
var bone_l_lower_arm := -1
var bone_r_lower_arm := -1
var bone_l_eye := -1
var bone_r_eye := -1

# Cached rest poses so procedural animation layers on top of the bind pose
var rest_pose: Dictionary = {}     # bone_idx -> Transform3D

# State driven by the Python server
var current_state := "idle"
var state_text := ""
var last_state := ""

# Animation clocks
var t := 0.0                       # global time accumulator
var blink_timer := 0.0
var next_blink := 4.0
var talk_phase := 0.0
var gaze_target := Vector2.ZERO    # current eye yaw/pitch
var gaze_next := Vector2.ZERO      # next eye target
var gaze_cooldown := 0.0
var gesture_phase := 0.0           # used during talking for hand gestures
var weight_shift := 0.0            # slow lateral hip sway

# Window-aware behaviour
var behaviour: int = BehaviourState.IDLE_FREESTAND
var focused_title := ""
var focused_rect := Rect2i()       # left/top/right/bottom in screen pixels
var focused_state := "normal"       # normal|maximized|minimized
var has_target := false
var perch_dwell := 0.0             # time spent perched on the same window
var last_perch_title := ""
var walk_phase := 0.0              # arm-swing accumulator while walking
var reaction_timer := 0.0          # one-shot reaction blend timer
var reaction_kind := ""             # wave|turn|surprise


func _ready() -> void:
	# Belt-and-braces: project.godot also enables transparent BG, but doing
	# it here keeps the scene self-contained.
	get_tree().get_root().transparent_bg = true
	RenderingServer.set_default_clear_color(Color(0, 0, 0, 0))

	status_poll.request_completed.connect(_on_status_completed)
	chat_post.request_completed.connect(_on_chat_completed)
	poll_timer.timeout.connect(_poll_status)
	chat_input.text_submitted.connect(_send_chat)
	window_poll.request_completed.connect(_on_window_completed)
	window_control_post.request_completed.connect(_on_window_control_completed)
	window_timer.timeout.connect(_poll_window)

	_resolve_avatar()


func _process(delta: float) -> void:
	t += delta

	if skeleton == null:
		return

	# Always-on layer: breathing + gaze + idle micro-sway. These run during
	# every state so the avatar never freezes into a mannequin.
	_drive_breathing()
	_drive_gaze(delta)
	_drive_idle_sway()

	match current_state:
		"talking":
			_drive_talking(delta)
		"thinking":
			_drive_thinking(delta)
		_:
			_drive_idle(delta)

	_drive_blink(delta)
	_drive_behaviour(delta)
	_drive_reaction(delta)


# ── Avatar resolution ──────────────────────────────────────────────────
func _resolve_avatar() -> void:
	if avatar_root.get_child_count() == 0:
		reply_label.text = "Drop a .vrm under the Avatar node in pet.tscn."
		return
	avatar_node = avatar_root.get_child(0)
	skeleton = _find_skeleton(avatar_node)
	blend_meshes.clear()
	_collect_blend_meshes(avatar_node)

	if skeleton:
		_resolve_bones()
		_cache_rest_pose()
	else:
		push_warning("No Skeleton3D found under avatar — body movement disabled.")


func _find_skeleton(node: Node) -> Skeleton3D:
	if node is Skeleton3D:
		return node
	for child in node.get_children():
		var s := _find_skeleton(child)
		if s:
			return s
	return null


func _collect_blend_meshes(node: Node) -> void:
	if node is MeshInstance3D:
		var mi: MeshInstance3D = node
		var mesh := mi.mesh
		if mesh and mesh.get_blend_shape_count() > 0:
			blend_meshes.append(mi)
	for child in node.get_children():
		_collect_blend_meshes(child)


# Resolves a bone by trying each candidate name. VRM rigs use either the
# Humanoid standard names ("Head", "LeftUpperArm") or the Japanese MMD-ish
# names ("J_Bip_C_Head", "J_Bip_L_UpperArm"). We try both.
func _resolve_bone(names: Array) -> int:
	for nm in names:
		var idx: int = skeleton.find_bone(nm)
		if idx >= 0:
			return idx
	return -1


func _resolve_bones() -> void:
	bone_head        = _resolve_bone(["Head", "head", "J_Bip_C_Head"])
	bone_neck        = _resolve_bone(["Neck", "neck", "J_Bip_C_Neck"])
	bone_upper_chest = _resolve_bone(["UpperChest", "J_Bip_C_UpperChest"])
	bone_chest       = _resolve_bone(["Chest", "J_Bip_C_Chest"])
	bone_spine       = _resolve_bone(["Spine", "J_Bip_C_Spine"])
	bone_hips        = _resolve_bone(["Hips", "hips", "J_Bip_C_Hips"])
	bone_l_shoulder  = _resolve_bone(["LeftShoulder",  "J_Bip_L_Shoulder"])
	bone_r_shoulder  = _resolve_bone(["RightShoulder", "J_Bip_R_Shoulder"])
	bone_l_upper_arm = _resolve_bone(["LeftUpperArm",  "J_Bip_L_UpperArm"])
	bone_r_upper_arm = _resolve_bone(["RightUpperArm", "J_Bip_R_UpperArm"])
	bone_l_lower_arm = _resolve_bone(["LeftLowerArm",  "J_Bip_L_LowerArm"])
	bone_r_lower_arm = _resolve_bone(["RightLowerArm", "J_Bip_R_LowerArm"])
	bone_l_eye       = _resolve_bone(["LeftEye",  "J_Adj_L_FaceEye", "J_Bip_L_Eye"])
	bone_r_eye       = _resolve_bone(["RightEye", "J_Adj_R_FaceEye", "J_Bip_R_Eye"])


func _cache_rest_pose() -> void:
	# Snapshot the bind pose so every per-frame rotation is applied as
	# rest * delta — never absolute. Otherwise we'd "drift" the avatar.
	rest_pose.clear()
	var bones := [
		bone_head, bone_neck, bone_chest, bone_upper_chest, bone_spine, bone_hips,
		bone_l_shoulder, bone_r_shoulder,
		bone_l_upper_arm, bone_r_upper_arm,
		bone_l_lower_arm, bone_r_lower_arm,
		bone_l_eye, bone_r_eye,
	]
	for b in bones:
		if b >= 0:
			rest_pose[b] = skeleton.get_bone_pose(b)


# ── Skeletal animation primitives ──────────────────────────────────────
func _set_bone_rotation(bone_idx: int, euler: Vector3) -> void:
	# Apply (rest * euler) — keeps the bind pose intact.
	if bone_idx < 0 or not rest_pose.has(bone_idx):
		return
	var rest: Transform3D = rest_pose[bone_idx]
	var rot := Basis.from_euler(euler)
	var t2 := Transform3D(rest.basis * rot, rest.origin)
	skeleton.set_bone_pose_position(bone_idx, t2.origin)
	skeleton.set_bone_pose_rotation(bone_idx, t2.basis.get_rotation_quaternion())


func _add_bone_position(bone_idx: int, offset: Vector3) -> void:
	if bone_idx < 0 or not rest_pose.has(bone_idx):
		return
	var rest: Transform3D = rest_pose[bone_idx]
	skeleton.set_bone_pose_position(bone_idx, rest.origin + offset)


# ── Always-on layers ──────────────────────────────────────────────────
func _drive_breathing() -> void:
	# Slow chest rise — sine wave at ~0.25 Hz
	var breath := sin(t * 1.6) * 0.025
	# Tilt the chest back slightly on inhale
	_set_bone_rotation(bone_chest, Vector3(-breath * 0.5, 0.0, 0.0))
	_set_bone_rotation(bone_upper_chest, Vector3(-breath * 0.4, 0.0, 0.0))
	# Slight vertical offset on the hips so the whole torso lifts a hair
	_add_bone_position(bone_hips, Vector3(0.0, breath * 0.4, 0.0))


func _drive_gaze(delta: float) -> void:
	# Pick a new gaze target every 1.5–4 s, then ease toward it.
	gaze_cooldown -= delta
	if gaze_cooldown <= 0.0:
		gaze_cooldown = randf_range(1.5, 4.0)
		gaze_next = Vector2(
			randf_range(-0.18, 0.18),     # yaw
			randf_range(-0.08, 0.10)      # pitch
		)
	gaze_target = gaze_target.lerp(gaze_next, clampf(delta * 4.0, 0.0, 1.0))

	# Eyes drive most of the gaze; head adds a subtle follow.
	_set_bone_rotation(bone_l_eye, Vector3(-gaze_target.y, gaze_target.x, 0.0))
	_set_bone_rotation(bone_r_eye, Vector3(-gaze_target.y, gaze_target.x, 0.0))


func _drive_idle_sway() -> void:
	# Slow lateral weight shift in the hips — the "I'm standing here" look.
	weight_shift = sin(t * 0.6) * 0.05
	_set_bone_rotation(bone_hips, Vector3(0.0, weight_shift * 0.3, weight_shift))
	_set_bone_rotation(bone_spine, Vector3(0.0, -weight_shift * 0.15, -weight_shift * 0.4))


# ── State drivers ──────────────────────────────────────────────────────
func _drive_idle(_delta: float) -> void:
	if last_state != "idle":
		_zero_mouth()
		_set_shape(["Joy", "joy", "Fun", "fun"], 0.18)
		_set_shape(["Sorrow", "sorrow"], 0.0)
		last_state = "idle"

	# Soft head bob + gentle arm float
	var head_yaw := sin(t * 0.8) * 0.06
	var head_pitch := sin(t * 1.1) * 0.03
	_set_bone_rotation(bone_head, Vector3(head_pitch, head_yaw, 0.0))
	_set_bone_rotation(bone_neck, Vector3(head_pitch * 0.4, head_yaw * 0.5, 0.0))

	# Arms relaxed at the side with a tiny sway
	var arm := sin(t * 0.7) * 0.04
	_set_bone_rotation(bone_l_upper_arm, Vector3(0.0, 0.0,  arm))
	_set_bone_rotation(bone_r_upper_arm, Vector3(0.0, 0.0, -arm))


func _drive_thinking(delta: float) -> void:
	if last_state != "thinking":
		_zero_mouth()
		_set_shape(["Fun", "fun", "Joy", "joy"], 0.0)
		_set_shape(["Sorrow", "sorrow"], 0.25)
		last_state = "thinking"

	# Head tilted, looking up-and-to-the-side as if reasoning
	var tilt := -0.18
	var look := sin(t * 0.5) * 0.05 - 0.10
	_set_bone_rotation(bone_head, Vector3(-0.05, look, tilt))
	_set_bone_rotation(bone_neck, Vector3(-0.03, look * 0.5, tilt * 0.4))

	# Right hand drifts up to chin — fold the elbow
	var fold := lerpf(0.0, 1.6, clampf(t * 0.5, 0.0, 1.0))
	_set_bone_rotation(bone_r_upper_arm, Vector3(-0.4, 0.2, -0.6))
	_set_bone_rotation(bone_r_lower_arm, Vector3(0.0,  -fold, 0.0))
	# Left arm relaxed
	_set_bone_rotation(bone_l_upper_arm, Vector3(0.0, 0.0, 0.05))


func _drive_talking(delta: float) -> void:
	if last_state != "talking":
		_set_shape(["Joy", "joy", "Fun", "fun"], 0.4)
		_set_shape(["Sorrow", "sorrow"], 0.0)
		last_state = "talking"

	# Sine-wave the "A" mouth shape as a quick lipsync stand-in
	talk_phase += delta * 12.0
	var v := (sin(talk_phase) * 0.5 + 0.5) * 0.7
	_set_shape(["A", "a", "aa", "Mouth_A"], v)

	# Head nods and turns while speaking
	var nod := sin(t * 3.2) * 0.05
	var turn := sin(t * 1.4) * 0.10
	_set_bone_rotation(bone_head, Vector3(nod, turn, 0.0))
	_set_bone_rotation(bone_neck, Vector3(nod * 0.5, turn * 0.5, 0.0))

	# Hand gestures — both arms rise and gesture in counterpoint
	gesture_phase += delta * 1.8
	var g := sin(gesture_phase)
	# Lift shoulders + arms forward, with one hand leading
	_set_bone_rotation(bone_l_upper_arm, Vector3(-0.5 - g * 0.15, 0.1, 0.4))
	_set_bone_rotation(bone_r_upper_arm, Vector3(-0.5 + g * 0.15, -0.1, -0.4))
	# Bend elbows
	_set_bone_rotation(bone_l_lower_arm, Vector3(0.0,  1.1 + g * 0.2, 0.0))
	_set_bone_rotation(bone_r_lower_arm, Vector3(0.0, -1.1 - g * 0.2, 0.0))


# ── Blink ──────────────────────────────────────────────────────────────
var _blinking := false
var _blink_phase := 0.0
func _drive_blink(delta: float) -> void:
	blink_timer += delta
	if not _blinking and blink_timer >= next_blink:
		_blinking = true
		_blink_phase = 0.0
	if _blinking:
		_blink_phase += delta * 8.0  # full blink ~0.4 s
		var v := sin(clampf(_blink_phase, 0.0, PI))
		_set_shape(["Blink", "blink", "Blink_L", "blinkLeft"], v)
		_set_shape(["Blink_R", "blinkRight"], v)
		if _blink_phase >= PI:
			_blinking = false
			blink_timer = 0.0
			next_blink = randf_range(3.5, 6.5)
			_set_shape(["Blink", "blink", "Blink_L", "blinkLeft"], 0.0)
			_set_shape(["Blink_R", "blinkRight"], 0.0)


# ── Blend shape helpers ────────────────────────────────────────────────
func _set_shape(name_options: Array, value: float) -> void:
	for mi in blend_meshes:
		var mesh := mi.mesh
		if mesh == null:
			continue
		var count: int = mesh.get_blend_shape_count()
		for nm in name_options:
			var idx := -1
			for i in count:
				if mesh.get_blend_shape_name(i) == nm:
					idx = i
					break
			if idx >= 0:
				mi.set_blend_shape_value(idx, value)
				break


func _zero_mouth() -> void:
	_set_shape(["A", "a", "aa", "Mouth_A"], 0.0)
	_set_shape(["I", "i", "ih", "Mouth_I"], 0.0)
	_set_shape(["U", "u", "ou", "Mouth_U"], 0.0)
	_set_shape(["E", "e", "ee", "Mouth_E"], 0.0)
	_set_shape(["O", "o", "oh", "Mouth_O"], 0.0)


# ── HTTP polling ───────────────────────────────────────────────────────
func _poll_status() -> void:
	status_poll.request(STATUS_URL)


func _on_status_completed(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if code != 200:
		return
	var txt := body.get_string_from_utf8()
	var data: Variant = JSON.parse_string(txt)
	if typeof(data) != TYPE_DICTIONARY:
		return
	current_state = str(data.get("state", "idle"))
	var new_text: String = str(data.get("text", ""))
	if new_text != state_text and new_text != "":
		state_text = new_text
		reply_label.text = state_text


# ── Chat send ──────────────────────────────────────────────────────────
func _send_chat(text: String) -> void:
	var msg := text.strip_edges()
	if msg == "":
		return
	chat_input.text = ""
	reply_label.text = "You: %s" % msg
	var payload := JSON.stringify({"message": msg})
	var headers := PackedStringArray(["Content-Type: application/json"])
	chat_post.request(CHAT_URL, headers, HTTPClient.METHOD_POST, payload)


func _on_chat_completed(_result: int, code: int, _headers: PackedStringArray, _body: PackedByteArray) -> void:
	if code != 200:
		reply_label.text = "[chat HTTP %d — is zendaya.py running?]" % code

# ── Window-aware behaviour ─────────────────────────────────────────────
func _poll_window() -> void:
	if not auto_follow:
		return
	window_poll.request(WINDOW_URL)


func _on_window_completed(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if code != 200:
		return
	var data: Variant = JSON.parse_string(body.get_string_from_utf8())
	if typeof(data) != TYPE_DICTIONARY:
		return

	var focused: Variant = data.get("focused", {})
	if typeof(focused) == TYPE_DICTIONARY and focused.has("title"):
		focused_title = str(focused.get("title", ""))
		focused_state = str(focused.get("state", "normal"))
		var rect_arr: Variant = focused.get("rect", [])
		if typeof(rect_arr) == TYPE_ARRAY and rect_arr.size() == 4:
			var l: int = int(rect_arr[0])
			var top: int = int(rect_arr[1])
			var r: int = int(rect_arr[2])
			var b: int = int(rect_arr[3])
			focused_rect = Rect2i(Vector2i(l, top), Vector2i(maxi(0, r - l), maxi(0, b - top)))
			has_target = true
		else:
			has_target = false
	else:
		has_target = false

	var events: Variant = data.get("events", [])
	if typeof(events) == TYPE_ARRAY:
		for ev in events:
			_handle_window_event(ev)


func _handle_window_event(ev: Variant) -> void:
	if typeof(ev) != TYPE_DICTIONARY:
		return
	var kind := str(ev.get("kind", ""))
	match kind:
		"focus_changed":
			_trigger_reaction("wave", 0.6)
		"window_opened":
			_trigger_reaction("turn", 0.5)
		"window_closed":
			_trigger_reaction("surprise", 0.4)


func _trigger_reaction(kind: String, dur: float) -> void:
	reaction_kind = kind
	reaction_timer = dur
	# Wake up if asleep
	if behaviour == BehaviourState.SLEEP:
		behaviour = BehaviourState.PERCH
		perch_dwell = 0.0


func _drive_reaction(delta: float) -> void:
	if reaction_timer <= 0.0:
		return
	reaction_timer -= delta
	match reaction_kind:
		"wave":
			# Quick right-hand wave
			_set_bone_rotation(bone_r_upper_arm, Vector3(-0.9, 0.0, -0.7))
			_set_bone_rotation(bone_r_lower_arm, Vector3(0.0, -1.4 + sin(t * 18.0) * 0.4, 0.0))
		"turn":
			_set_bone_rotation(bone_head, Vector3(0.0, 0.5, 0.0))
			_set_bone_rotation(bone_neck, Vector3(0.0, 0.25, 0.0))
		"surprise":
			_set_shape(["Surprised", "surprised", "Fun", "fun"], 1.0)
			_set_shape(["A", "a", "Mouth_A"], 0.4)
	if reaction_timer <= 0.0:
		_set_shape(["Surprised", "surprised"], 0.0)


func _drive_behaviour(delta: float) -> void:
	if not auto_follow:
		behaviour = BehaviourState.IDLE_FREESTAND
		return

	# Skip self / no usable target → freestanding
	var skip_self: bool = focused_title == SELF_TITLE or focused_title == ""
	var unusable: bool = not has_target or focused_state == "minimized" or focused_rect.size.x <= 0
	if skip_self or unusable:
		behaviour = BehaviourState.IDLE_FREESTAND
		perch_dwell = 0.0
		return

	# Compute desired screen position above the target's title bar.
	var win_size: Vector2i = DisplayServer.window_get_size()
	var desired := Vector2i(
		focused_rect.position.x + 40,
		maxi(0, focused_rect.position.y - win_size.y + 24)
	)
	var current_pos: Vector2i = DisplayServer.window_get_position()
	var dist: float = Vector2(current_pos - desired).length()

	# State transitions
	if focused_title != last_perch_title:
		# New target — walk to it.
		behaviour = BehaviourState.WALK
		perch_dwell = 0.0
	elif behaviour == BehaviourState.WALK and dist <= ARRIVE_RADIUS:
		behaviour = BehaviourState.PERCH
		perch_dwell = 0.0
		_trigger_reaction("turn", 0.3)
	elif behaviour == BehaviourState.PERCH:
		if dist > ARRIVE_RADIUS * 3.0:
			# Window jumped (resized/moved) — re-walk
			behaviour = BehaviourState.WALK
			perch_dwell = 0.0
		else:
			perch_dwell += delta
			if perch_dwell >= SLEEP_AFTER and current_state == "idle":
				behaviour = BehaviourState.SLEEP
	elif behaviour == BehaviourState.SLEEP:
		if current_state != "idle":
			behaviour = BehaviourState.PERCH
			perch_dwell = 0.0
	else:
		behaviour = BehaviourState.WALK

	last_perch_title = focused_title

	# Movement rates (pixels per second feel — applied as lerp factor)
	var speed: float = 0.0
	match behaviour:
		BehaviourState.WALK:
			speed = 4.0
			walk_phase += delta * 6.0
			# Arm-swing overlay
			var sw := sin(walk_phase) * 0.35
			_set_bone_rotation(bone_l_upper_arm, Vector3(sw, 0.0, 0.05))
			_set_bone_rotation(bone_r_upper_arm, Vector3(-sw, 0.0, -0.05))
		BehaviourState.PERCH:
			speed = 8.0
		BehaviourState.SLEEP:
			speed = 8.0
			# Head drops, eyes closed
			_set_bone_rotation(bone_head, Vector3(0.45, 0.0, 0.05))
			_set_bone_rotation(bone_neck, Vector3(0.25, 0.0, 0.0))
			_set_shape(["Blink", "blink", "Blink_L", "blinkLeft"], 1.0)
			_set_shape(["Blink_R", "blinkRight"], 1.0)
			if reply_label.text == "" or not reply_label.text.begins_with("💤"):
				reply_label.text = "💤"
		_:
			return

	# Lerp the OS window position toward the target.
	var k: float = clampf(delta * speed, 0.0, 1.0)
	var new_pos := Vector2i(
		int(round(lerpf(float(current_pos.x), float(desired.x), k))),
		int(round(lerpf(float(current_pos.y), float(desired.y), k)))
	)
	if new_pos != current_pos:
		DisplayServer.window_set_position(new_pos)


func _on_window_control_completed(_result: int, _code: int, _headers: PackedStringArray, _body: PackedByteArray) -> void:
	pass


func _send_window_control(action: String, title: String) -> void:
	var payload := JSON.stringify({"action": action, "title": title})
	var headers := PackedStringArray(["Content-Type: application/json"])
	window_control_post.request(WINDOW_CONTROL_URL, headers, HTTPClient.METHOD_POST, payload)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		var mb: InputEventMouseButton = event
		if focused_title == "" or focused_title == SELF_TITLE:
			return
		if mb.button_index == MOUSE_BUTTON_LEFT:
			_send_window_control("focus", focused_title)
			_trigger_reaction("wave", 0.4)
		elif mb.button_index == MOUSE_BUTTON_RIGHT:
			_send_window_control("minimize", focused_title)
			_trigger_reaction("turn", 0.3)


# ─────────────────────────────────────────────────────────────────────
# Switching between Zendaya.vrm and Zendaya-orange.vrm:
#   Open pet.tscn → delete current child of "Avatar" → drag the other
#   imported .vrm scene under Avatar → save. The script auto-discovers
#   bones and blend shapes at runtime.
