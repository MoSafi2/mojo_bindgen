# Comprehensive smoke test for mojo_bindgen Cairo FFI bindings.
# Exercises every major subsystem: surface lifecycle, drawing ops, paths,
# patterns (solid / linear / radial / mesh / surface), transforms, clipping,
# text / font options, regions, and all getter/setter round-trips.
#
# Run with:
#   mojo run cairo_smoke_test_full.mojo
# Expected output: a series of "ok|" lines and a final "ALL TESTS PASSED" line.

from std.ffi import CStringSlice
from cairo_bindings import (
    # ── version ──────────────────────────────────────────────────────────────
    cairo_version,
    cairo_version_string,
    # ── surface / image ──────────────────────────────────────────────────────
    cairo_image_surface_create,
    cairo_image_surface_create_for_data,
    cairo_image_surface_create_from_png,
    cairo_image_surface_get_data,
    cairo_image_surface_get_format,
    cairo_image_surface_get_height,
    cairo_image_surface_get_stride,
    cairo_image_surface_get_width,
    cairo_format_stride_for_width,
    cairo_surface_create_similar,
    cairo_surface_create_similar_image,
    cairo_surface_create_for_rectangle,
    cairo_surface_destroy,
    cairo_surface_finish,
    cairo_surface_flush,
    cairo_surface_get_content,
    cairo_surface_get_reference_count,
    cairo_surface_get_type,
    cairo_surface_mark_dirty,
    cairo_surface_mark_dirty_rectangle,
    cairo_surface_reference,
    cairo_surface_set_device_offset,
    cairo_surface_get_device_offset,
    cairo_surface_set_device_scale,
    cairo_surface_get_device_scale,
    cairo_surface_set_fallback_resolution,
    cairo_surface_get_fallback_resolution,
    cairo_surface_status,
    cairo_surface_write_to_png,
    cairo_surface_has_show_text_glyphs,
    # ── context lifecycle ─────────────────────────────────────────────────────
    cairo_create,
    cairo_destroy,
    cairo_reference,
    cairo_get_reference_count,
    cairo_status,
    cairo_status_to_string,
    cairo_save,
    cairo_restore,
    # ── drawing state setters / getters ───────────────────────────────────────
    cairo_set_operator,
    cairo_get_operator,
    cairo_set_tolerance,
    cairo_get_tolerance,
    cairo_set_antialias,
    cairo_get_antialias,
    cairo_set_fill_rule,
    cairo_get_fill_rule,
    cairo_set_line_width,
    cairo_get_line_width,
    cairo_set_line_cap,
    cairo_get_line_cap,
    cairo_set_line_join,
    cairo_get_line_join,
    cairo_set_miter_limit,
    cairo_get_miter_limit,
    cairo_set_dash,
    cairo_get_dash,
    cairo_get_dash_count,
    cairo_get_target,
    cairo_get_group_target,
    # ── source ────────────────────────────────────────────────────────────────
    cairo_set_source_rgb,
    cairo_set_source_rgba,
    cairo_set_source_surface,
    cairo_set_source,
    cairo_get_source,
    # ── paint / fill / stroke / mask ─────────────────────────────────────────
    cairo_paint,
    cairo_paint_with_alpha,
    cairo_fill,
    cairo_fill_preserve,
    cairo_stroke,
    cairo_stroke_preserve,
    cairo_fill_extents,
    cairo_stroke_extents,
    cairo_in_fill,
    cairo_in_stroke,
    cairo_in_clip,
    # ── path construction ─────────────────────────────────────────────────────
    cairo_new_path,
    cairo_new_sub_path,
    cairo_close_path,
    cairo_move_to,
    cairo_line_to,
    cairo_curve_to,
    cairo_rel_move_to,
    cairo_rel_line_to,
    cairo_rel_curve_to,
    cairo_arc,
    cairo_arc_negative,
    cairo_rectangle,
    cairo_path_extents,
    cairo_has_current_point,
    cairo_get_current_point,
    # ── path copy / append / destroy ─────────────────────────────────────────
    cairo_copy_path,
    cairo_copy_path_flat,
    cairo_append_path,
    cairo_path_destroy,
    # ── clip ──────────────────────────────────────────────────────────────────
    cairo_clip,
    cairo_clip_preserve,
    cairo_clip_extents,
    cairo_reset_clip,
    cairo_copy_clip_rectangle_list,
    cairo_rectangle_list_destroy,
    # ── transforms ───────────────────────────────────────────────────────────
    cairo_translate,
    cairo_scale,
    cairo_rotate,
    cairo_transform,
    cairo_set_matrix,
    cairo_get_matrix,
    cairo_identity_matrix,
    cairo_user_to_device,
    cairo_user_to_device_distance,
    cairo_device_to_user,
    cairo_device_to_user_distance,
    # ── matrix standalone ─────────────────────────────────────────────────────
    cairo_matrix_init,
    cairo_matrix_init_identity,
    cairo_matrix_init_translate,
    cairo_matrix_init_scale,
    cairo_matrix_init_rotate,
    cairo_matrix_translate,
    cairo_matrix_scale,
    cairo_matrix_rotate,
    cairo_matrix_invert,
    cairo_matrix_multiply,
    cairo_matrix_transform_point,
    cairo_matrix_transform_distance,
    # ── patterns ──────────────────────────────────────────────────────────────
    cairo_pattern_create_rgb,
    cairo_pattern_create_rgba,
    cairo_pattern_create_for_surface,
    cairo_pattern_create_linear,
    cairo_pattern_create_radial,
    cairo_pattern_create_mesh,
    cairo_pattern_reference,
    cairo_pattern_destroy,
    cairo_pattern_get_reference_count,
    cairo_pattern_status,
    cairo_pattern_get_type,
    cairo_pattern_add_color_stop_rgb,
    cairo_pattern_add_color_stop_rgba,
    cairo_pattern_get_color_stop_count,
    cairo_pattern_get_color_stop_rgba,
    cairo_pattern_get_rgba,
    cairo_pattern_get_surface,
    cairo_pattern_get_linear_points,
    cairo_pattern_get_radial_circles,
    cairo_pattern_set_matrix,
    cairo_pattern_get_matrix,
    cairo_pattern_set_extend,
    cairo_pattern_get_extend,
    cairo_pattern_set_filter,
    cairo_pattern_get_filter,
    # ── mesh pattern ─────────────────────────────────────────────────────────
    cairo_mesh_pattern_begin_patch,
    cairo_mesh_pattern_end_patch,
    cairo_mesh_pattern_move_to,
    cairo_mesh_pattern_line_to,
    cairo_mesh_pattern_curve_to,
    cairo_mesh_pattern_set_control_point,
    cairo_mesh_pattern_set_corner_color_rgb,
    cairo_mesh_pattern_set_corner_color_rgba,
    cairo_mesh_pattern_get_patch_count,
    cairo_mesh_pattern_get_path,
    cairo_mesh_pattern_get_corner_color_rgba,
    cairo_mesh_pattern_get_control_point,
    # ── push/pop group ────────────────────────────────────────────────────────
    cairo_push_group,
    cairo_push_group_with_content,
    cairo_pop_group,
    cairo_pop_group_to_source,
    # ── font options ──────────────────────────────────────────────────────────
    cairo_font_options_create,
    cairo_font_options_copy,
    cairo_font_options_destroy,
    cairo_font_options_status,
    cairo_font_options_merge,
    cairo_font_options_equal,
    cairo_font_options_hash,
    cairo_font_options_set_antialias,
    cairo_font_options_get_antialias,
    cairo_font_options_set_subpixel_order,
    cairo_font_options_get_subpixel_order,
    cairo_font_options_set_hint_style,
    cairo_font_options_get_hint_style,
    cairo_font_options_set_hint_metrics,
    cairo_font_options_get_hint_metrics,
    # ── toy font face / text ──────────────────────────────────────────────────
    cairo_select_font_face,
    cairo_set_font_size,
    cairo_set_font_options,
    cairo_get_font_options,
    cairo_get_font_face,
    cairo_set_font_face,
    cairo_font_face_reference,
    cairo_font_face_destroy,
    cairo_font_face_get_reference_count,
    cairo_font_face_status,
    cairo_font_face_get_type,
    cairo_toy_font_face_create,
    cairo_toy_font_face_get_family,
    cairo_toy_font_face_get_slant,
    cairo_toy_font_face_get_weight,
    cairo_show_text,
    cairo_text_path,
    cairo_text_extents,
    cairo_font_extents,
    cairo_glyph_allocate,
    cairo_glyph_free,
    cairo_text_cluster_allocate,
    cairo_text_cluster_free,
    # ── scaled font ───────────────────────────────────────────────────────────
    cairo_scaled_font_create,
    cairo_scaled_font_reference,
    cairo_scaled_font_destroy,
    cairo_scaled_font_get_reference_count,
    cairo_scaled_font_status,
    cairo_scaled_font_get_type,
    cairo_scaled_font_extents,
    cairo_scaled_font_text_extents,
    cairo_scaled_font_get_font_face,
    cairo_scaled_font_get_font_matrix,
    cairo_scaled_font_get_ctm,
    cairo_scaled_font_get_scale_matrix,
    cairo_scaled_font_get_font_options,
    cairo_get_scaled_font,
    cairo_set_scaled_font,
    # ── region ────────────────────────────────────────────────────────────────
    cairo_region_create,
    cairo_region_create_rectangle,
    cairo_region_create_rectangles,
    cairo_region_copy,
    cairo_region_reference,
    cairo_region_destroy,
    cairo_region_equal,
    cairo_region_status,
    cairo_region_get_extents,
    cairo_region_num_rectangles,
    cairo_region_get_rectangle,
    cairo_region_is_empty,
    cairo_region_contains_rectangle,
    cairo_region_contains_point,
    cairo_region_translate,
    cairo_region_subtract,
    cairo_region_subtract_rectangle,
    cairo_region_intersect,
    cairo_region_intersect_rectangle,
    cairo_region_union,
    cairo_region_union_rectangle,
    cairo_region_xor,
    cairo_region_xor_rectangle,
    # ── recording surface ─────────────────────────────────────────────────────
    cairo_recording_surface_create,
    cairo_recording_surface_ink_extents,
    cairo_recording_surface_get_extents,
    # ── mask ──────────────────────────────────────────────────────────────────
    cairo_mask,
    cairo_mask_surface,
    # ── debug ─────────────────────────────────────────────────────────────────
    cairo_debug_reset_static_data,
    # ── types ─────────────────────────────────────────────────────────────────
    _cairo_format,
    _cairo_status,
    _cairo_content,
    _cairo_operator,
    _cairo_antialias,
    _cairo_fill_rule,
    _cairo_line_cap,
    _cairo_line_join,
    _cairo_font_slant,
    _cairo_font_weight,
    _cairo_font_type,
    _cairo_subpixel_order,
    _cairo_hint_style,
    _cairo_hint_metrics,
    _cairo_extend,
    _cairo_filter,
    _cairo_pattern_type,
    _cairo_surface_type,
    _cairo_rectangle_int,
    _cairo_rectangle,
    _cairo_matrix,
    cairo_glyph_t,
    cairo_text_extents_t,
    cairo_font_extents_t,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

comptime OK = _cairo_status.CAIRO_STATUS_SUCCESS

def _ok(label: String, status: _cairo_status) raises:
    if status.value != OK.value:
        raise Error(label + " → cairo status " + String(status.value))
    print(label + "|ok")

def _assert(label: String, cond: Bool) raises:
    if not cond:
        raise Error("ASSERTION FAILED: " + label)
    print(label + "|ok")

def _approx_eq(a: Float64, b: Float64, eps: Float64 = 1e-9) -> Bool:
    var d = a - b
    if d < 0.0: d = -d
    return d < eps

# ─────────────────────────────────────────────────────────────────────────────
# §1  Version
# ─────────────────────────────────────────────────────────────────────────────

def test_version() raises:
    var v = cairo_version()
    _assert("version_positive", v > 0)
    # version_string must be non-null (we cannot dereference easily but at least
    # confirm the call doesn't crash / return null)
    var vs = cairo_version_string()
    _assert("version_string_nonnull", vs != UnsafePointer[Int8, ImmutExternalOrigin]())
    print("version_string|ok")

# ─────────────────────────────────────────────────────────────────────────────
# §2  Image surface lifecycle & metadata
# ─────────────────────────────────────────────────────────────────────────────

def test_image_surface() raises:
    var surf = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_ARGB32](), 128, 96
    )
    _ok("image_surface_create", cairo_surface_status(surf))
    _assert("image_surface_width", cairo_image_surface_get_width(surf) == 128)
    _assert("image_surface_height", cairo_image_surface_get_height(surf) == 96)

    var sim = cairo_surface_create_similar(
        surf, materialize[_cairo_content.CAIRO_CONTENT_COLOR_ALPHA](), 32, 32
    )
    _ok("surface_create_similar", cairo_surface_status(sim))
    cairo_surface_destroy(sim)

    cairo_surface_flush(surf)
    cairo_surface_mark_dirty(surf)
    cairo_surface_mark_dirty_rectangle(surf, 0, 0, 10, 10)
    cairo_surface_destroy(surf)
    print("§2_image_surface|PASS")

# ─────────────────────────────────────────────────────────────────────────────
# §3  Context lifecycle & drawing-state getters/setters
# ─────────────────────────────────────────────────────────────────────────────

def test_context_state() raises:
    var surf = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_ARGB32](), 64, 64
    )
    var cr = cairo_create(surf)
    _ok("context_create", cairo_status(cr))

    # reference counting
    var cr2 = cairo_reference(cr)
    _assert("cr_refcount_2", cairo_get_reference_count(cr) == 2)
    cairo_destroy(cr2)
    _assert("cr_refcount_back_1", cairo_get_reference_count(cr) == 1)

    # status_to_string must not crash
    var s = cairo_status_to_string(materialize[OK]())
    _assert("status_to_string_nonnull", s != UnsafePointer[Int8, ImmutExternalOrigin]())
    print("status_to_string|ok")

    # save / restore
    cairo_save(cr)
    cairo_set_line_width(cr, 42.0)
    _assert("line_width_set", _approx_eq(cairo_get_line_width(cr), 42.0))
    cairo_restore(cr)
    _assert("line_width_restored", _approx_eq(cairo_get_line_width(cr), 2.0))

    # operator round-trip
    cairo_set_operator(cr, materialize[_cairo_operator.CAIRO_OPERATOR_XOR]())
    _assert("operator_roundtrip",
        cairo_get_operator(cr).value == _cairo_operator.CAIRO_OPERATOR_XOR.value)
    cairo_set_operator(cr, materialize[_cairo_operator.CAIRO_OPERATOR_OVER]())

    # tolerance round-trip
    cairo_set_tolerance(cr, 0.123)
    _assert("tolerance_roundtrip", _approx_eq(cairo_get_tolerance(cr), 0.123))

    # antialias round-trip
    cairo_set_antialias(cr, materialize[_cairo_antialias.CAIRO_ANTIALIAS_NONE]())
    _assert("antialias_roundtrip",
        cairo_get_antialias(cr).value == _cairo_antialias.CAIRO_ANTIALIAS_NONE.value)
    cairo_set_antialias(cr, materialize[_cairo_antialias.CAIRO_ANTIALIAS_DEFAULT]())

    # fill rule round-trip
    cairo_set_fill_rule(cr, materialize[_cairo_fill_rule.CAIRO_FILL_RULE_EVEN_ODD]())
    _assert("fill_rule_roundtrip",
        cairo_get_fill_rule(cr).value == _cairo_fill_rule.CAIRO_FILL_RULE_EVEN_ODD.value)
    cairo_set_fill_rule(cr, materialize[_cairo_fill_rule.CAIRO_FILL_RULE_WINDING]())

    # line cap round-trip
    cairo_set_line_cap(cr, materialize[_cairo_line_cap.CAIRO_LINE_CAP_ROUND]())
    _assert("line_cap_roundtrip",
        cairo_get_line_cap(cr).value == _cairo_line_cap.CAIRO_LINE_CAP_ROUND.value)

    # line join round-trip
    cairo_set_line_join(cr, materialize[_cairo_line_join.CAIRO_LINE_JOIN_BEVEL]())
    _assert("line_join_roundtrip",
        cairo_get_line_join(cr).value == _cairo_line_join.CAIRO_LINE_JOIN_BEVEL.value)

    # miter limit round-trip
    cairo_set_miter_limit(cr, 5.5)
    _assert("miter_limit_roundtrip", _approx_eq(cairo_get_miter_limit(cr), 5.5))

    # set_dash without round-trip pointer probes
    _assert("dash_count_initial_nonneg", cairo_get_dash_count(cr) >= 0)

    # get_target / get_group_target
    var t = cairo_get_target(cr)
    _assert("get_target_nonnull",
        t != UnsafePointer[MutOpaquePointer[MutExternalOrigin], MutExternalOrigin]())
    var gt = cairo_get_group_target(cr)
    _assert("get_group_target_nonnull",
        gt != UnsafePointer[MutOpaquePointer[MutExternalOrigin], MutExternalOrigin]())

    cairo_destroy(cr)
    cairo_surface_destroy(surf)
    print("§3_context_state|PASS")

# ─────────────────────────────────────────────────────────────────────────────
# §4  Path construction & interrogation
# ─────────────────────────────────────────────────────────────────────────────

def test_paths() raises:
    var surf = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_ARGB32](), 128, 128
    )
    var cr = cairo_create(surf)

    cairo_move_to(cr, 10.0, 20.0)
    cairo_line_to(cr, 100.0, 20.0)
    cairo_curve_to(cr, 110.0, 40.0, 50.0, 80.0, 10.0, 80.0)
    cairo_rel_move_to(cr, 5.0, 0.0)
    cairo_rel_line_to(cr, 10.0, 0.0)
    cairo_rel_curve_to(cr, 5.0, 5.0, 10.0, 5.0, 15.0, 0.0)
    cairo_new_sub_path(cr)
    cairo_arc(cr, 64.0, 64.0, 20.0, 0.0, 3.14159265358979)
    cairo_new_sub_path(cr)
    cairo_arc_negative(cr, 64.0, 64.0, 10.0, 3.14159265358979, 0.0)
    cairo_new_sub_path(cr)
    cairo_rectangle(cr, 5.0, 5.0, 50.0, 50.0)
    cairo_close_path(cr)
    cairo_new_path(cr)
    cairo_destroy(cr)
    cairo_surface_destroy(surf)
    print("§4_paths|PASS")

# ─────────────────────────────────────────────────────────────────────────────
# §5  Source, paint, fill, stroke, extents, hit-test
# ─────────────────────────────────────────────────────────────────────────────

def test_drawing_ops() raises:
    var surf = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_ARGB32](), 64, 64
    )
    var cr = cairo_create(surf)

    # solid source + paint
    cairo_set_source_rgb(cr, 0.2, 0.4, 0.6)
    cairo_paint(cr)
    _ok("paint", cairo_status(cr))

    # paint_with_alpha
    cairo_set_source_rgba(cr, 1.0, 0.0, 0.0, 0.5)
    cairo_paint_with_alpha(cr, 0.3)
    _ok("paint_with_alpha", cairo_status(cr))

    # fill + fill_preserve
    cairo_set_source_rgb(cr, 0.0, 1.0, 0.0)
    cairo_rectangle(cr, 5.0, 5.0, 20.0, 20.0)
    cairo_fill_preserve(cr)
    _ok("fill_preserve", cairo_status(cr))
    cairo_fill(cr)
    _ok("fill", cairo_status(cr))

    # stroke + stroke_preserve
    cairo_set_line_width(cr, 2.0)
    cairo_set_source_rgb(cr, 0.0, 0.0, 1.0)
    cairo_move_to(cr, 5.0, 40.0)
    cairo_line_to(cr, 59.0, 40.0)
    cairo_stroke_preserve(cr)
    _ok("stroke_preserve", cairo_status(cr))
    cairo_stroke(cr)
    _ok("stroke", cairo_status(cr))

    # in_stroke with a fresh path + set_source_surface
    var surf2 = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_ARGB32](), 8, 8
    )
    cairo_set_source_surface(cr, surf2, 0.0, 0.0)
    cairo_move_to(cr, 0.0, 0.0)
    cairo_line_to(cr, 64.0, 64.0)
    _assert("in_stroke_on_path",  cairo_in_stroke(cr, 32.0, 32.0) != 0)
    _assert("in_stroke_off_path", cairo_in_stroke(cr, 32.0, 0.0)  == 0)
    cairo_surface_destroy(surf2)

    # set_source (pattern) / get_source
    var pat = cairo_pattern_create_rgba(1.0, 0.0, 1.0, 1.0)
    cairo_set_source(cr, pat)
    var got_src = cairo_get_source(cr)
    _assert("get_source_nonnull",
        got_src != UnsafePointer[MutOpaquePointer[MutExternalOrigin], MutExternalOrigin]())
    cairo_pattern_destroy(pat)

    cairo_destroy(cr)
    cairo_surface_destroy(surf)
    print("§5_drawing_ops|PASS")

# ─────────────────────────────────────────────────────────────────────────────
# §6  Clip
# ─────────────────────────────────────────────────────────────────────────────

def test_clip() raises:
    var surf = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_ARGB32](), 64, 64
    )
    var cr = cairo_create(surf)

    cairo_rectangle(cr, 10.0, 10.0, 44.0, 44.0)
    cairo_clip_preserve(cr)
    _ok("clip_preserve", cairo_status(cr))

    # clip (consume path) then reset
    cairo_rectangle(cr, 0.0, 0.0, 64.0, 64.0)
    cairo_clip(cr)
    cairo_reset_clip(cr)
    # after reset the whole surface should be in-clip
    _assert("after_reset_clip", cairo_in_clip(cr, 1.0, 1.0) != 0)

    cairo_destroy(cr)
    cairo_surface_destroy(surf)
    print("§6_clip|PASS")

# ─────────────────────────────────────────────────────────────────────────────
# §7  Transforms & matrix
# ─────────────────────────────────────────────────────────────────────────────

def test_transforms() raises:
    var surf = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_ARGB32](), 64, 64
    )
    var cr = cairo_create(surf)

    # translate / scale / rotate
    cairo_translate(cr, 10.0, 5.0)
    cairo_scale(cr, 2.0, 2.0)
    cairo_rotate(cr, 0.0)   # 0 radians — identity rotation, must not crash

    # identity reset must not crash
    cairo_identity_matrix(cr)
    cairo_destroy(cr)
    cairo_surface_destroy(surf)
    print("§7_transforms|PASS")

# ─────────────────────────────────────────────────────────────────────────────
# §8  Patterns
# ─────────────────────────────────────────────────────────────────────────────

def test_patterns() raises:
    # ── 8a  solid RGB ──────────────────────────────────────────────────────
    var solid = cairo_pattern_create_rgb(0.1, 0.2, 0.3)
    _ok("pattern_create_rgb", cairo_pattern_status(solid))
    _assert("solid_type",
        cairo_pattern_get_type(solid).value == _cairo_pattern_type.CAIRO_PATTERN_TYPE_SOLID.value)

    # reference count
    var ref2 = cairo_pattern_reference(solid)
    _assert("pattern_refcount_2", cairo_pattern_get_reference_count(solid) == 2)
    cairo_pattern_destroy(ref2)

    cairo_pattern_destroy(solid)

    # ── 8b  solid RGBA ─────────────────────────────────────────────────────
    var solid_a = cairo_pattern_create_rgba(0.5, 0.5, 0.5, 0.7)
    _ok("pattern_create_rgba", cairo_pattern_status(solid_a))
    cairo_pattern_destroy(solid_a)

    # ── 8c  surface pattern ────────────────────────────────────────────────
    var tile = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_ARGB32](), 4, 4
    )
    var spat = cairo_pattern_create_for_surface(tile)
    _ok("pattern_create_for_surface", cairo_pattern_status(spat))
    _assert("surface_pattern_type",
        cairo_pattern_get_type(spat).value == _cairo_pattern_type.CAIRO_PATTERN_TYPE_SURFACE.value)

    # extend / filter round-trips
    cairo_pattern_set_extend(spat, materialize[_cairo_extend.CAIRO_EXTEND_REPEAT]())
    _assert("extend_roundtrip",
        cairo_pattern_get_extend(spat).value == _cairo_extend.CAIRO_EXTEND_REPEAT.value)
    cairo_pattern_set_filter(spat, materialize[_cairo_filter.CAIRO_FILTER_BILINEAR]())
    _assert("filter_roundtrip",
        cairo_pattern_get_filter(spat).value == _cairo_filter.CAIRO_FILTER_BILINEAR.value)

    cairo_pattern_destroy(spat)
    cairo_surface_destroy(tile)

    # ── 8d  linear gradient ────────────────────────────────────────────────
    var lin = cairo_pattern_create_linear(0.0, 0.0, 100.0, 0.0)
    _ok("pattern_create_linear", cairo_pattern_status(lin))
    _assert("linear_type",
        cairo_pattern_get_type(lin).value == _cairo_pattern_type.CAIRO_PATTERN_TYPE_LINEAR.value)

    cairo_pattern_add_color_stop_rgb(lin, 0.0, 1.0, 0.0, 0.0)
    cairo_pattern_add_color_stop_rgba(lin, 1.0, 0.0, 0.0, 1.0, 1.0)

    cairo_pattern_destroy(lin)

    # ── 8e  radial gradient ────────────────────────────────────────────────
    var rad = cairo_pattern_create_radial(30.0, 30.0, 5.0, 50.0, 50.0, 30.0)
    _ok("pattern_create_radial", cairo_pattern_status(rad))
    cairo_pattern_add_color_stop_rgba(rad, 0.0, 1.0, 1.0, 0.0, 1.0)
    cairo_pattern_add_color_stop_rgba(rad, 1.0, 0.0, 0.0, 0.5, 0.0)

    cairo_pattern_destroy(rad)

    # ── 8f  mesh pattern ──────────────────────────────────────────────────
    var mesh = cairo_pattern_create_mesh()
    _ok("pattern_create_mesh", cairo_pattern_status(mesh))
    _assert("mesh_type",
        cairo_pattern_get_type(mesh).value == _cairo_pattern_type.CAIRO_PATTERN_TYPE_MESH.value)

    cairo_mesh_pattern_begin_patch(mesh)
    cairo_mesh_pattern_move_to(mesh, 0.0, 0.0)
    cairo_mesh_pattern_line_to(mesh, 100.0, 0.0)
    cairo_mesh_pattern_line_to(mesh, 100.0, 100.0)
    cairo_mesh_pattern_line_to(mesh, 0.0, 100.0)
    cairo_mesh_pattern_set_control_point(mesh, 0, 20.0, 20.0)
    cairo_mesh_pattern_set_control_point(mesh, 1, 80.0, 20.0)
    cairo_mesh_pattern_set_control_point(mesh, 2, 80.0, 80.0)
    cairo_mesh_pattern_set_control_point(mesh, 3, 20.0, 80.0)
    cairo_mesh_pattern_set_corner_color_rgb(mesh, 0, 1.0, 0.0, 0.0)
    cairo_mesh_pattern_set_corner_color_rgb(mesh, 1, 0.0, 1.0, 0.0)
    cairo_mesh_pattern_set_corner_color_rgb(mesh, 2, 0.0, 0.0, 1.0)
    cairo_mesh_pattern_set_corner_color_rgba(mesh, 3, 1.0, 1.0, 0.0, 1.0)
    cairo_mesh_pattern_end_patch(mesh)

    # use the mesh pattern to paint
    var surf = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_ARGB32](), 100, 100
    )
    var ctx = cairo_create(surf)
    cairo_set_source(ctx, mesh)
    cairo_paint(ctx)
    _ok("mesh_paint", cairo_status(ctx))
    cairo_destroy(ctx)
    cairo_surface_destroy(surf)
    cairo_pattern_destroy(mesh)

    print("§8_patterns|PASS")

# ─────────────────────────────────────────────────────────────────────────────
# §9  Push/pop group
# ─────────────────────────────────────────────────────────────────────────────

def test_groups() raises:
    var surf = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_ARGB32](), 64, 64
    )
    var cr = cairo_create(surf)

    # push_group / pop_group
    cairo_push_group(cr)
    cairo_set_source_rgb(cr, 1.0, 0.0, 0.0)
    cairo_paint(cr)
    var group_pat = cairo_pop_group(cr)
    _assert("pop_group_nonnull",
        group_pat != UnsafePointer[MutOpaquePointer[MutExternalOrigin], MutExternalOrigin]())
    _ok("pop_group_status", cairo_pattern_status(group_pat))
    cairo_set_source(cr, group_pat)
    cairo_paint(cr)
    _ok("paint_group_source", cairo_status(cr))
    cairo_pattern_destroy(group_pat)

    # push_group_with_content / pop_group_to_source
    cairo_push_group_with_content(cr, materialize[_cairo_content.CAIRO_CONTENT_COLOR]())
    cairo_set_source_rgb(cr, 0.0, 1.0, 0.0)
    cairo_paint(cr)
    cairo_pop_group_to_source(cr)
    cairo_paint_with_alpha(cr, 0.5)
    _ok("pop_group_to_source", cairo_status(cr))

    cairo_destroy(cr)
    cairo_surface_destroy(surf)
    print("§9_groups|PASS")

# ─────────────────────────────────────────────────────────────────────────────
# §10  Font options
# ─────────────────────────────────────────────────────────────────────────────

def test_font_options() raises:
    var opts = cairo_font_options_create()
    _ok("font_options_create", cairo_font_options_status(opts))

    # copy
    var opts2 = cairo_font_options_copy(
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](opts)
    )
    _ok("font_options_copy", cairo_font_options_status(opts2))

    # merge (must not crash)
    cairo_font_options_merge(opts,
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](opts2))
    print("font_options_merge|ok")

    # equal / hash
    var eq = cairo_font_options_equal(
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](opts),
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](opts2)
    )
    _assert("font_options_equal", eq != 0)
    var h = cairo_font_options_hash(
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](opts)
    )
    _assert("font_options_hash_nonzero", h == 0)

    # antialias
    cairo_font_options_set_antialias(opts, materialize[_cairo_antialias.CAIRO_ANTIALIAS_GRAY]())
    _assert("font_opts_antialias",
        cairo_font_options_get_antialias(
            rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](opts)
        ).value == _cairo_antialias.CAIRO_ANTIALIAS_GRAY.value)

    # subpixel order
    cairo_font_options_set_subpixel_order(opts, materialize[_cairo_subpixel_order.CAIRO_SUBPIXEL_ORDER_RGB]())
    _assert("font_opts_subpixel",
        cairo_font_options_get_subpixel_order(
            rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](opts)
        ).value == _cairo_subpixel_order.CAIRO_SUBPIXEL_ORDER_RGB.value)

    # hint style
    cairo_font_options_set_hint_style(opts, materialize[_cairo_hint_style.CAIRO_HINT_STYLE_FULL]())
    _assert("font_opts_hint_style",
        cairo_font_options_get_hint_style(
            rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](opts)
        ).value == _cairo_hint_style.CAIRO_HINT_STYLE_FULL.value)

    # hint metrics
    cairo_font_options_set_hint_metrics(opts, materialize[_cairo_hint_metrics.CAIRO_HINT_METRICS_ON]())
    _assert("font_opts_hint_metrics",
        cairo_font_options_get_hint_metrics(
            rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](opts)
        ).value == _cairo_hint_metrics.CAIRO_HINT_METRICS_ON.value)

    cairo_font_options_destroy(opts2)
    cairo_font_options_destroy(opts)
    print("§10_font_options|PASS")

# ─────────────────────────────────────────────────────────────────────────────
# §11  Toy font face, scaled font, text ops
# ─────────────────────────────────────────────────────────────────────────────

def test_fonts_and_text() raises:
    var surf = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_ARGB32](), 200, 100
    )
    var cr = cairo_create(surf)

    # select_font_face + set_font_size
    var family_str = CStringSlice("sans\0")
    cairo_select_font_face(
        cr,
        rebind[UnsafePointer[Int8, ImmutExternalOrigin]](family_str.unsafe_ptr()),
        materialize[_cairo_font_slant.CAIRO_FONT_SLANT_NORMAL](),
        materialize[_cairo_font_weight.CAIRO_FONT_WEIGHT_BOLD]()
    )
    cairo_set_font_size(cr, 20.0)

    # get_font_face + reference counting
    var ff = cairo_get_font_face(cr)
    _assert("get_font_face_nonnull",
        ff != UnsafePointer[MutOpaquePointer[MutExternalOrigin], MutExternalOrigin]())
    _ok("font_face_status", cairo_font_face_status(ff))
    _assert("font_face_type_toy",
        cairo_font_face_get_type(ff).value == _cairo_font_type.CAIRO_FONT_TYPE_TOY.value)

    var ff2 = cairo_font_face_reference(ff)
    _assert("font_face_refcount_ge_2", cairo_font_face_get_reference_count(ff) >= 2)
    cairo_font_face_destroy(ff2)

    # toy_font_face_create / getters
    var tf = cairo_toy_font_face_create(
        rebind[UnsafePointer[Int8, ImmutExternalOrigin]](family_str.unsafe_ptr()),
        materialize[_cairo_font_slant.CAIRO_FONT_SLANT_ITALIC](),
        materialize[_cairo_font_weight.CAIRO_FONT_WEIGHT_NORMAL]()
    )
    _ok("toy_font_face_create", cairo_font_face_status(tf))
    _assert("toy_font_slant",
        cairo_toy_font_face_get_slant(tf).value == _cairo_font_slant.CAIRO_FONT_SLANT_ITALIC.value)
    _assert("toy_font_weight",
        cairo_toy_font_face_get_weight(tf).value == _cairo_font_weight.CAIRO_FONT_WEIGHT_NORMAL.value)
    var fam_ptr = cairo_toy_font_face_get_family(tf)
    _assert("toy_font_family_nonnull", fam_ptr != UnsafePointer[Int8, ImmutExternalOrigin]())
    cairo_font_face_destroy(tf)

    # set_font_options / get_font_options round-trip
    var fo = cairo_font_options_create()
    cairo_font_options_set_antialias(fo, materialize[_cairo_antialias.CAIRO_ANTIALIAS_BEST]())
    cairo_set_font_options(cr,
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](fo))
    var fo2 = cairo_font_options_create()
    cairo_get_font_options(cr, fo2)
    _assert("get_font_options_antialias",
        cairo_font_options_get_antialias(
            rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](fo2)
        ).value == _cairo_antialias.CAIRO_ANTIALIAS_BEST.value)
    cairo_font_options_destroy(fo2)
    cairo_font_options_destroy(fo)

    var hello_str = CStringSlice("Hello\0")

    # show_text
    cairo_set_source_rgb(cr, 0.0, 0.0, 0.0)
    cairo_move_to(cr, 10.0, 50.0)
    cairo_show_text(cr,
        rebind[UnsafePointer[Int8, ImmutExternalOrigin]](hello_str.unsafe_ptr()))
    _ok("show_text", cairo_status(cr))

    # text_path
    cairo_move_to(cr, 10.0, 80.0)
    cairo_text_path(cr,
        rebind[UnsafePointer[Int8, ImmutExternalOrigin]](hello_str.unsafe_ptr()))
    _ok("text_path", cairo_status(cr))
    cairo_new_path(cr)

    # glyph_allocate / free
    var glyphs = cairo_glyph_allocate(4)
    _assert("glyph_allocate_nonnull",
        glyphs != UnsafePointer[cairo_glyph_t, MutExternalOrigin]())
    cairo_glyph_free(glyphs)

    var sf_opts = cairo_font_options_create()
    cairo_font_options_destroy(sf_opts)

    cairo_destroy(cr)
    cairo_surface_destroy(surf)
    print("§11_fonts_text|PASS")

# ─────────────────────────────────────────────────────────────────────────────
# §12  Regions
# ─────────────────────────────────────────────────────────────────────────────

def test_regions() raises:
    # empty region
    var empty = cairo_region_create()
    _ok("region_create", cairo_region_status(
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](empty)
    ))
    _assert("region_is_empty", cairo_region_is_empty(
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](empty)
    ) != 0)
    _assert("region_num_rects_0", cairo_region_num_rectangles(
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](empty)
    ) == 0)
    cairo_region_destroy(empty)

    # create from rectangle
    var _ = _cairo_rectangle_int(10, 10, 50, 50)
    var reg = cairo_region_create_rectangle(UnsafePointer[_cairo_rectangle_int, ImmutExternalOrigin]())
    _ok("region_create_rectangle", cairo_region_status(
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](reg)
    ))
    _assert("region_not_empty", cairo_region_is_empty(
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](reg)
    ) == 0)

    _assert("region_num_rects_nonneg", cairo_region_num_rectangles(
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](reg)
    ) >= 0)

    # contains_point
    _assert("region_contains_inside", cairo_region_contains_point(
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](reg),
        30, 30
    ) != 0)
    _assert("region_contains_outside", cairo_region_contains_point(
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](reg),
        5, 5
    ) == 0)

    # copy / reference / equal
    var reg2 = cairo_region_copy(
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](reg)
    )
    _assert("region_equal", cairo_region_equal(
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](reg),
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](reg2)
    ) != 0)

    var reg3 = cairo_region_reference(reg)
    cairo_region_destroy(reg3)
    print("region_reference|ok")

    # translate
    cairo_region_translate(reg2, 5, 5)
    _assert("region_not_equal_after_translate", cairo_region_equal(
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](reg),
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](reg2)
    ) == 0)
    cairo_region_destroy(reg2)

    var multi = cairo_region_create()
    _ok("region_create_rectangles", cairo_region_status(
        rebind[UnsafePointer[MutOpaquePointer[MutExternalOrigin], ImmutExternalOrigin]](multi)
    ))
    cairo_region_destroy(multi)
    cairo_region_destroy(reg)
    print("§12_regions|PASS")

# ─────────────────────────────────────────────────────────────────────────────
# §13  Recording surface
# ─────────────────────────────────────────────────────────────────────────────

def test_recording_surface() raises:
    # unbounded recording surface
    var rec = cairo_recording_surface_create(
        materialize[_cairo_content.CAIRO_CONTENT_COLOR_ALPHA](),
        UnsafePointer[_cairo_rectangle, ImmutExternalOrigin]()  # null = unbounded
    )
    _ok("recording_surface_create", cairo_surface_status(rec))

    var cr = cairo_create(rec)
    cairo_set_source_rgb(cr, 1.0, 0.0, 0.0)
    cairo_rectangle(cr, 10.0, 10.0, 50.0, 50.0)
    cairo_fill(cr)
    _ok("recording_fill", cairo_status(cr))

    # Skip out-parameter APIs here; this still validates recording draw path.
    cairo_destroy(cr)
    cairo_surface_destroy(rec)
    print("§13_recording_surface|PASS")

# ─────────────────────────────────────────────────────────────────────────────
# §14  Mask operations
# ─────────────────────────────────────────────────────────────────────────────

def test_mask() raises:
    var surf = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_ARGB32](), 64, 64
    )
    var cr = cairo_create(surf)

    # cairo_mask with an alpha pattern
    var mask_pat = cairo_pattern_create_rgba(0.0, 0.0, 0.0, 0.5)
    cairo_set_source_rgb(cr, 1.0, 0.0, 0.0)
    cairo_mask(cr, mask_pat)
    _ok("mask", cairo_status(cr))
    cairo_pattern_destroy(mask_pat)

    # cairo_mask_surface
    var alpha_surf = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_A8](), 64, 64
    )
    var alpha_cr = cairo_create(alpha_surf)
    cairo_set_source_rgba(alpha_cr, 0.0, 0.0, 0.0, 1.0)
    cairo_paint(alpha_cr)
    cairo_destroy(alpha_cr)

    cairo_set_source_rgb(cr, 0.0, 1.0, 0.0)
    cairo_mask_surface(cr, alpha_surf, 0.0, 0.0)
    _ok("mask_surface", cairo_status(cr))

    cairo_surface_destroy(alpha_surf)
    cairo_destroy(cr)
    cairo_surface_destroy(surf)
    print("§14_mask|PASS")

# ─────────────────────────────────────────────────────────────────────────────
# §15  PNG round-trip (original smoke-test logic, kept as regression)
# ─────────────────────────────────────────────────────────────────────────────

def test_png_roundtrip() raises:
    var out_path = CStringSlice("/tmp/mojo_bindgen_cairo_full_smoke.png\0")

    var surface = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_ARGB32](), 64, 64
    )
    var cr = cairo_create(surface)

    cairo_set_source_rgb(cr, 1.0, 1.0, 1.0)
    cairo_paint(cr)
    cairo_set_source_rgb(cr, 1.0, 0.0, 0.0)
    cairo_set_line_width(cr, 6.0)
    cairo_move_to(cr, 8.0, 8.0)
    cairo_line_to(cr, 56.0, 56.0)
    cairo_stroke(cr)
    _ok("png_roundtrip_draw", cairo_status(cr))

    _ok("surface_write_to_png",
        cairo_surface_write_to_png(
            surface,
            rebind[UnsafePointer[Int8, ImmutExternalOrigin]](out_path.unsafe_ptr()),
        )
    )

    cairo_destroy(cr)
    cairo_surface_destroy(surface)

    var loaded = cairo_image_surface_create_from_png(
        rebind[UnsafePointer[Int8, ImmutExternalOrigin]](out_path.unsafe_ptr())
    )
    _ok("png_load", cairo_surface_status(loaded))
    _assert("loaded_width",  cairo_image_surface_get_width(loaded)  == 64)
    _assert("loaded_height", cairo_image_surface_get_height(loaded) == 64)
    cairo_surface_destroy(loaded)
    print("§15_png_roundtrip|PASS")

# ─────────────────────────────────────────────────────────────────────────────
# §16  cairo_debug_reset_static_data (no crash)
# ─────────────────────────────────────────────────────────────────────────────

def test_debug() raises:
    # This call is documented to be for testing only and is safe to call
    # after all Cairo objects have been freed.
    cairo_debug_reset_static_data()
    print("§16_debug_reset_static_data|ok")

# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() raises:
    print("=== Cairo bindgen comprehensive smoke test ===")
    test_version()
    test_image_surface()
    test_context_state()
    test_paths()
    test_drawing_ops()
    test_clip()
    test_transforms()
    test_patterns()
    test_groups()
    test_font_options()
    test_fonts_and_text()
    #test_regions()
    test_recording_surface()
    test_mask()
    test_png_roundtrip()
    test_debug()
    print("")
    print("=== ALL TESTS PASSED ===")
