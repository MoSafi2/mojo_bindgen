# Compact composite smoke test for mojo_bindgen Cairo FFI bindings.
# Exercises major Cairo subsystems in grouped checks and one shared image.

from std.ffi import CStringSlice
from std.memory import alloc
from cairo_bindings import (
    cairo_version,
    cairo_version_string,
    cairo_debug_reset_static_data,
    cairo_image_surface_create,
    cairo_image_surface_create_from_png,
    cairo_image_surface_get_height,
    cairo_image_surface_get_width,
    cairo_surface_create_similar,
    cairo_surface_destroy,
    cairo_surface_status,
    cairo_surface_write_to_png,
    cairo_surface_flush,
    cairo_surface_mark_dirty,
    cairo_surface_mark_dirty_rectangle,
    cairo_create,
    cairo_destroy,
    cairo_reference,
    cairo_get_reference_count,
    cairo_status,
    cairo_status_to_string,
    cairo_save,
    cairo_restore,
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
    cairo_get_dash_count,
    cairo_get_target,
    cairo_get_group_target,
    cairo_set_source_rgb,
    cairo_set_source_rgba,
    cairo_set_source_surface,
    cairo_set_source,
    cairo_get_source,
    cairo_paint,
    cairo_paint_with_alpha,
    cairo_fill,
    cairo_fill_preserve,
    cairo_stroke,
    cairo_stroke_preserve,
    cairo_in_stroke,
    cairo_in_clip,
    cairo_mask,
    cairo_mask_surface,
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
    cairo_clip,
    cairo_clip_preserve,
    cairo_reset_clip,
    cairo_translate,
    cairo_scale,
    cairo_rotate,
    cairo_identity_matrix,
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
    cairo_pattern_set_extend,
    cairo_pattern_get_extend,
    cairo_pattern_set_filter,
    cairo_pattern_get_filter,
    cairo_pattern_get_surface,
    cairo_pattern_get_linear_points,
    cairo_pattern_get_radial_circles,
    cairo_pattern_get_rgba,
    cairo_pattern_set_matrix,
    cairo_pattern_get_matrix,
    cairo_mesh_pattern_begin_patch,
    cairo_mesh_pattern_end_patch,
    cairo_mesh_pattern_move_to,
    cairo_mesh_pattern_line_to,
    cairo_mesh_pattern_set_control_point,
    cairo_mesh_pattern_set_corner_color_rgb,
    cairo_mesh_pattern_set_corner_color_rgba,
    cairo_mesh_pattern_get_patch_count,
    cairo_push_group,
    cairo_push_group_with_content,
    cairo_pop_group,
    cairo_pop_group_to_source,
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
    cairo_select_font_face,
    cairo_set_font_size,
    cairo_get_font_face,
    cairo_font_face_reference,
    cairo_font_face_destroy,
    cairo_font_face_get_reference_count,
    cairo_font_face_status,
    cairo_font_face_get_type,
    cairo_toy_font_face_create,
    cairo_toy_font_face_get_slant,
    cairo_toy_font_face_get_weight,
    cairo_toy_font_face_get_family,
    cairo_show_text,
    cairo_text_path,
    cairo_glyph_allocate,
    cairo_glyph_free,
    cairo_region_create,
    cairo_region_create_rectangle,
    cairo_region_copy,
    cairo_region_destroy,
    cairo_region_reference,
    cairo_region_status,
    cairo_region_get_extents,
    cairo_region_num_rectangles,
    cairo_region_is_empty,
    cairo_region_contains_point,
    cairo_region_equal,
    cairo_region_translate,
    cairo_recording_surface_create,
    cairo_glyph_t,
    cairo_t,
    cairo_surface_t,
    cairo_pattern_t,
    cairo_font_options_t,
    _cairo_status,
    _cairo_format,
    _cairo_content,
    _cairo_operator,
    _cairo_antialias,
    _cairo_fill_rule,
    _cairo_line_cap,
    _cairo_line_join,
    _cairo_extend,
    _cairo_filter,
    _cairo_pattern_type,
    _cairo_subpixel_order,
    _cairo_hint_style,
    _cairo_hint_metrics,
    _cairo_font_slant,
    _cairo_font_weight,
    _cairo_font_type,
    _cairo_matrix,
    _cairo_rectangle_int,
    _cairo_rectangle,
)

comptime OK = _cairo_status.CAIRO_STATUS_SUCCESS
comptime SCENE_W = 960
comptime SCENE_H = 640


def _ok(label: String, status: _cairo_status) raises:
    if status.value != OK.value:
        raise Error(label + " -> cairo status " + String(status.value))
    print(label + "|ok")


def _assert(label: String, cond: Bool) raises:
    if not cond:
        raise Error("ASSERTION FAILED: " + label)
    print(label + "|ok")


def _approx_eq(a: Float64, b: Float64, eps: Float64 = 1e-9) -> Bool:
    var d = a - b
    if d < 0.0:
        d = -d
    return d < eps


def _draw_panel_border(
    cr: UnsafePointer[cairo_t, MutExternalOrigin],
    x: Float64,
    y: Float64,
    w: Float64,
    h: Float64,
):
    cairo_save(cr)
    cairo_set_source_rgb(cr, 0.3, 0.3, 0.3)
    cairo_set_line_width(cr, 1.0)
    cairo_rectangle(cr, x, y, w, h)
    cairo_stroke(cr)
    cairo_restore(cr)


def run_metadata_and_lifecycle_checks() raises:
    _assert("version_positive", cairo_version() > 0)
    _assert(
        "version_string_nonnull",
        cairo_version_string() != UnsafePointer[Int8, ImmutExternalOrigin](),
    )

    var surf = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_ARGB32](), 96, 96
    )
    _ok("base_surface_create", cairo_surface_status(surf))
    var sim = cairo_surface_create_similar(
        surf, materialize[_cairo_content.CAIRO_CONTENT_COLOR_ALPHA](), 32, 32
    )
    _ok("surface_create_similar", cairo_surface_status(sim))
    cairo_surface_destroy(sim)
    cairo_surface_flush(surf)
    cairo_surface_mark_dirty(surf)
    cairo_surface_mark_dirty_rectangle(surf, 0, 0, 10, 10)

    var cr = cairo_create(surf)
    _ok("context_create", cairo_status(cr))
    var cr2 = cairo_reference(cr)
    _assert("context_refcount_2", cairo_get_reference_count(cr) == 2)
    cairo_destroy(cr2)
    _assert("context_refcount_1", cairo_get_reference_count(cr) == 1)
    _assert(
        "status_to_string_nonnull",
        cairo_status_to_string(materialize[OK]())
        != UnsafePointer[Int8, ImmutExternalOrigin](),
    )

    cairo_save(cr)
    cairo_set_line_width(cr, 7.0)
    _assert("line_width_set", _approx_eq(cairo_get_line_width(cr), 7.0))
    cairo_restore(cr)
    _assert("line_width_restored", _approx_eq(cairo_get_line_width(cr), 2.0))

    cairo_set_operator(cr, materialize[_cairo_operator.CAIRO_OPERATOR_XOR]())
    _assert(
        "operator_roundtrip",
        cairo_get_operator(cr).value
        == _cairo_operator.CAIRO_OPERATOR_XOR.value,
    )
    cairo_set_operator(cr, materialize[_cairo_operator.CAIRO_OPERATOR_OVER]())
    cairo_set_tolerance(cr, 0.25)
    _assert("tolerance_roundtrip", _approx_eq(cairo_get_tolerance(cr), 0.25))
    cairo_set_antialias(
        cr, materialize[_cairo_antialias.CAIRO_ANTIALIAS_NONE]()
    )
    _assert(
        "antialias_roundtrip",
        cairo_get_antialias(cr).value
        == _cairo_antialias.CAIRO_ANTIALIAS_NONE.value,
    )
    cairo_set_antialias(
        cr, materialize[_cairo_antialias.CAIRO_ANTIALIAS_DEFAULT]()
    )
    cairo_set_fill_rule(
        cr, materialize[_cairo_fill_rule.CAIRO_FILL_RULE_EVEN_ODD]()
    )
    _assert(
        "fill_rule_roundtrip",
        cairo_get_fill_rule(cr).value
        == _cairo_fill_rule.CAIRO_FILL_RULE_EVEN_ODD.value,
    )
    cairo_set_fill_rule(
        cr, materialize[_cairo_fill_rule.CAIRO_FILL_RULE_WINDING]()
    )
    cairo_set_line_cap(cr, materialize[_cairo_line_cap.CAIRO_LINE_CAP_ROUND]())
    _assert(
        "line_cap_roundtrip",
        cairo_get_line_cap(cr).value
        == _cairo_line_cap.CAIRO_LINE_CAP_ROUND.value,
    )
    cairo_set_line_join(
        cr, materialize[_cairo_line_join.CAIRO_LINE_JOIN_BEVEL]()
    )
    _assert(
        "line_join_roundtrip",
        cairo_get_line_join(cr).value
        == _cairo_line_join.CAIRO_LINE_JOIN_BEVEL.value,
    )
    cairo_set_miter_limit(cr, 5.5)
    _assert("miter_roundtrip", _approx_eq(cairo_get_miter_limit(cr), 5.5))
    _assert("dash_count_nonneg", cairo_get_dash_count(cr) >= 0)
    _assert(
        "get_target_nonnull",
        cairo_get_target(cr)
        != UnsafePointer[cairo_surface_t, MutExternalOrigin](),
    )
    _assert(
        "get_group_target_nonnull",
        cairo_get_group_target(cr)
        != UnsafePointer[cairo_surface_t, MutExternalOrigin](),
    )

    cairo_destroy(cr)
    cairo_surface_destroy(surf)
    print("metadata_lifecycle|PASS")


def draw_composite_scene(
    cr: UnsafePointer[cairo_t, MutExternalOrigin]
) raises:
    cairo_set_source_rgb(cr, 1.0, 1.0, 1.0)
    cairo_paint(cr)

    _draw_panel_border(cr, 20.0, 20.0, 300.0, 180.0)
    cairo_save(cr)
    cairo_translate(cr, 20.0, 20.0)
    cairo_move_to(cr, 20.0, 30.0)
    cairo_line_to(cr, 260.0, 30.0)
    cairo_curve_to(cr, 280.0, 70.0, 150.0, 120.0, 30.0, 120.0)
    cairo_rel_move_to(cr, 10.0, 0.0)
    cairo_rel_line_to(cr, 20.0, 0.0)
    cairo_rel_curve_to(cr, 5.0, 5.0, 10.0, 5.0, 15.0, 0.0)
    cairo_new_sub_path(cr)
    cairo_arc(cr, 140.0, 90.0, 36.0, 0.0, 3.14159265358979)
    cairo_new_sub_path(cr)
    cairo_arc_negative(cr, 140.0, 90.0, 20.0, 3.14159265358979, 0.0)
    cairo_close_path(cr)
    cairo_set_source_rgba(cr, 0.2, 0.7, 0.9, 0.35)
    cairo_fill_preserve(cr)
    _ok("panel1_fill_preserve", cairo_status(cr))
    cairo_set_line_width(cr, 2.5)
    cairo_set_source_rgb(cr, 0.1, 0.2, 0.7)
    cairo_stroke_preserve(cr)
    _ok("panel1_stroke_preserve", cairo_status(cr))
    _assert("panel1_in_stroke", cairo_in_stroke(cr, 140.0, 90.0) != 0)
    cairo_stroke(cr)
    cairo_new_path(cr)
    cairo_restore(cr)

    _draw_panel_border(cr, 340.0, 20.0, 300.0, 180.0)
    cairo_save(cr)
    cairo_translate(cr, 340.0, 20.0)
    var lin = cairo_pattern_create_linear(0.0, 0.0, 280.0, 0.0)
    _ok("pattern_linear_create", cairo_pattern_status(lin))
    _assert(
        "pattern_linear_type",
        cairo_pattern_get_type(lin).value
        == _cairo_pattern_type.CAIRO_PATTERN_TYPE_LINEAR.value,
    )
    cairo_pattern_add_color_stop_rgb(lin, 0.0, 1.0, 0.0, 0.0)
    cairo_pattern_add_color_stop_rgba(lin, 1.0, 0.0, 0.0, 1.0, 1.0)
    cairo_set_source(cr, lin)
    cairo_rectangle(cr, 10.0, 10.0, 280.0, 40.0)
    cairo_fill(cr)

    var rad = cairo_pattern_create_radial(70.0, 100.0, 8.0, 120.0, 120.0, 70.0)
    _ok("pattern_radial_create", cairo_pattern_status(rad))
    cairo_pattern_add_color_stop_rgba(rad, 0.0, 1.0, 1.0, 0.0, 1.0)
    cairo_pattern_add_color_stop_rgba(rad, 1.0, 0.0, 0.0, 0.5, 0.0)
    cairo_set_source(cr, rad)
    cairo_rectangle(cr, 10.0, 60.0, 130.0, 110.0)
    cairo_fill(cr)

    var mesh = cairo_pattern_create_mesh()
    _ok("pattern_mesh_create", cairo_pattern_status(mesh))
    cairo_mesh_pattern_begin_patch(mesh)
    cairo_mesh_pattern_move_to(mesh, 150.0, 60.0)
    cairo_mesh_pattern_line_to(mesh, 290.0, 60.0)
    cairo_mesh_pattern_line_to(mesh, 290.0, 170.0)
    cairo_mesh_pattern_line_to(mesh, 150.0, 170.0)
    cairo_mesh_pattern_set_control_point(mesh, 0, 170.0, 80.0)
    cairo_mesh_pattern_set_control_point(mesh, 1, 270.0, 80.0)
    cairo_mesh_pattern_set_control_point(mesh, 2, 270.0, 150.0)
    cairo_mesh_pattern_set_control_point(mesh, 3, 170.0, 150.0)
    cairo_mesh_pattern_set_corner_color_rgb(mesh, 0, 1.0, 0.0, 0.0)
    cairo_mesh_pattern_set_corner_color_rgb(mesh, 1, 0.0, 1.0, 0.0)
    cairo_mesh_pattern_set_corner_color_rgb(mesh, 2, 0.0, 0.0, 1.0)
    cairo_mesh_pattern_set_corner_color_rgba(mesh, 3, 1.0, 1.0, 0.0, 1.0)
    cairo_mesh_pattern_end_patch(mesh)
    var patch_count = alloc[UInt32](1)
    _ok(
        "mesh_patch_count",
        cairo_mesh_pattern_get_patch_count(mesh, patch_count),
    )
    _assert("mesh_patch_count_ge1", patch_count[] >= 1)
    patch_count.free()
    cairo_set_source(cr, mesh)
    cairo_paint_with_alpha(cr, 0.7)

    var tiny = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_ARGB32](), 8, 8
    )
    var tiny_cr = cairo_create(tiny)
    cairo_set_source_rgb(tiny_cr, 0.0, 0.0, 0.0)
    cairo_paint(tiny_cr)
    cairo_destroy(tiny_cr)

    var surface_pat = cairo_pattern_create_for_surface(tiny)
    _ok("pattern_surface_create", cairo_pattern_status(surface_pat))
    cairo_pattern_set_extend(
        surface_pat, materialize[_cairo_extend.CAIRO_EXTEND_REPEAT]()
    )
    _assert(
        "pattern_extend_roundtrip",
        cairo_pattern_get_extend(surface_pat).value
        == _cairo_extend.CAIRO_EXTEND_REPEAT.value,
    )
    cairo_pattern_set_filter(
        surface_pat, materialize[_cairo_filter.CAIRO_FILTER_BILINEAR]()
    )
    _assert(
        "pattern_filter_roundtrip",
        cairo_pattern_get_filter(surface_pat).value
        == _cairo_filter.CAIRO_FILTER_BILINEAR.value,
    )

    var p_ref = cairo_pattern_reference(surface_pat)
    _assert(
        "pattern_refcount_ge2",
        cairo_pattern_get_reference_count(surface_pat) >= 2,
    )
    cairo_pattern_destroy(p_ref)
    cairo_set_source(cr, surface_pat)
    cairo_rectangle(cr, 220.0, 70.0, 70.0, 70.0)
    cairo_fill(cr)

    var rgba_pat = cairo_pattern_create_rgba(0.8, 0.1, 0.8, 0.6)
    var sr = alloc[Float64](1)
    var sg = alloc[Float64](1)
    var sb = alloc[Float64](1)
    var sa = alloc[Float64](1)
    _ok(
        "pattern_get_rgba",
        cairo_pattern_get_rgba(rgba_pat, sr, sg, sb, sa),
    )
    var matrix = alloc[_cairo_matrix](1)
    cairo_pattern_get_matrix(rgba_pat, matrix)
    cairo_pattern_set_matrix(rgba_pat, matrix)
    var surf_ptr = alloc[UnsafePointer[cairo_surface_t, MutExternalOrigin]](1)
    _ok(
        "pattern_get_surface",
        cairo_pattern_get_surface(surface_pat, surf_ptr),
    )
    var x0 = alloc[Float64](1)
    var y0 = alloc[Float64](1)
    var x1 = alloc[Float64](1)
    var y1 = alloc[Float64](1)
    _ok(
        "pattern_get_linear_points",
        cairo_pattern_get_linear_points(lin, x0, y0, x1, y1),
    )
    var cx0 = alloc[Float64](1)
    var cy0 = alloc[Float64](1)
    var r0 = alloc[Float64](1)
    var cx1 = alloc[Float64](1)
    var cy1 = alloc[Float64](1)
    var r1 = alloc[Float64](1)
    _ok(
        "pattern_get_radial_circles",
        cairo_pattern_get_radial_circles(rad, cx0, cy0, r0, cx1, cy1, r1),
    )
    sr.free()
    sg.free()
    sb.free()
    sa.free()
    matrix.free()
    surf_ptr.free()
    x0.free()
    y0.free()
    x1.free()
    y1.free()
    cx0.free()
    cy0.free()
    r0.free()
    cx1.free()
    cy1.free()
    r1.free()

    cairo_pattern_destroy(rgba_pat)
    cairo_pattern_destroy(surface_pat)
    cairo_pattern_destroy(mesh)
    cairo_pattern_destroy(rad)
    cairo_pattern_destroy(lin)
    cairo_surface_destroy(tiny)
    cairo_restore(cr)

    _draw_panel_border(cr, 660.0, 20.0, 280.0, 180.0)
    cairo_save(cr)
    cairo_translate(cr, 660.0, 20.0)
    cairo_rectangle(cr, 20.0, 20.0, 120.0, 120.0)
    cairo_clip_preserve(cr)
    _ok("panel3_clip_preserve", cairo_status(cr))
    cairo_set_source_rgb(cr, 0.9, 0.9, 0.95)
    cairo_fill(cr)
    cairo_translate(cr, 40.0, 30.0)
    cairo_scale(cr, 1.2, 1.2)
    cairo_rotate(cr, 0.0)
    cairo_set_source_rgb(cr, 0.2, 0.2, 0.8)
    cairo_rectangle(cr, 0.0, 0.0, 80.0, 60.0)
    cairo_fill(cr)
    cairo_identity_matrix(cr)
    cairo_rectangle(cr, 0.0, 0.0, 280.0, 180.0)
    cairo_clip(cr)
    cairo_reset_clip(cr)
    _assert("panel3_after_reset_clip", cairo_in_clip(cr, 2.0, 2.0) != 0)
    cairo_restore(cr)

    _draw_panel_border(cr, 20.0, 220.0, 300.0, 180.0)
    cairo_save(cr)
    cairo_translate(cr, 20.0, 220.0)
    cairo_push_group(cr)
    cairo_set_source_rgb(cr, 1.0, 0.4, 0.4)
    cairo_paint(cr)
    var group_pat = cairo_pop_group(cr)
    _ok("panel4_pop_group_status", cairo_pattern_status(group_pat))
    cairo_set_source(cr, group_pat)
    cairo_paint(cr)
    cairo_pattern_destroy(group_pat)

    cairo_push_group_with_content(
        cr, materialize[_cairo_content.CAIRO_CONTENT_COLOR]()
    )
    cairo_set_source_rgb(cr, 0.1, 0.8, 0.2)
    cairo_rectangle(cr, 40.0, 30.0, 120.0, 100.0)
    cairo_fill(cr)
    cairo_pop_group_to_source(cr)
    cairo_paint_with_alpha(cr, 0.4)
    _ok("panel4_pop_group_to_source", cairo_status(cr))

    var source_probe = cairo_pattern_create_rgb(0.2, 0.2, 0.2)
    cairo_set_source(cr, source_probe)
    _assert(
        "panel4_get_source_nonnull",
        cairo_get_source(cr)
        != UnsafePointer[cairo_pattern_t, MutExternalOrigin](),
    )
    cairo_pattern_destroy(source_probe)
    cairo_restore(cr)

    _draw_panel_border(cr, 340.0, 220.0, 300.0, 180.0)
    cairo_save(cr)
    cairo_translate(cr, 340.0, 220.0)
    var mask_pat = cairo_pattern_create_rgba(0.0, 0.0, 0.0, 0.45)
    cairo_set_source_rgb(cr, 0.9, 0.1, 0.1)
    cairo_mask(cr, mask_pat)
    _ok("panel5_mask", cairo_status(cr))
    cairo_pattern_destroy(mask_pat)

    var alpha_surf = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_A8](), 280, 160
    )
    var alpha_cr = cairo_create(alpha_surf)
    cairo_set_source_rgba(alpha_cr, 0.0, 0.0, 0.0, 1.0)
    cairo_paint(alpha_cr)
    cairo_destroy(alpha_cr)
    cairo_set_source_rgb(cr, 0.0, 0.5, 0.0)
    cairo_mask_surface(cr, alpha_surf, 0.0, 0.0)
    _ok("panel5_mask_surface", cairo_status(cr))
    cairo_surface_destroy(alpha_surf)
    cairo_restore(cr)

    _draw_panel_border(cr, 660.0, 220.0, 280.0, 180.0)
    cairo_save(cr)
    cairo_translate(cr, 660.0, 220.0)
    var family = CStringSlice("sans\0")
    cairo_select_font_face(
        cr,
        rebind[UnsafePointer[Int8, ImmutExternalOrigin]](family.unsafe_ptr()),
        materialize[_cairo_font_slant.CAIRO_FONT_SLANT_NORMAL](),
        materialize[_cairo_font_weight.CAIRO_FONT_WEIGHT_BOLD](),
    )
    cairo_set_font_size(cr, 22.0)
    var ff = cairo_get_font_face(cr)
    _ok("panel6_font_face_status", cairo_font_face_status(ff))
    _assert(
        "panel6_font_face_toy",
        cairo_font_face_get_type(ff).value
        == _cairo_font_type.CAIRO_FONT_TYPE_TOY.value,
    )
    var ff2 = cairo_font_face_reference(ff)
    _assert(
        "panel6_font_refcount_ge2", cairo_font_face_get_reference_count(ff) >= 2
    )
    cairo_font_face_destroy(ff2)

    var tf = cairo_toy_font_face_create(
        rebind[UnsafePointer[Int8, ImmutExternalOrigin]](family.unsafe_ptr()),
        materialize[_cairo_font_slant.CAIRO_FONT_SLANT_ITALIC](),
        materialize[_cairo_font_weight.CAIRO_FONT_WEIGHT_NORMAL](),
    )
    _ok("panel6_toy_font_create", cairo_font_face_status(tf))
    _assert(
        "panel6_toy_slant",
        cairo_toy_font_face_get_slant(tf).value
        == _cairo_font_slant.CAIRO_FONT_SLANT_ITALIC.value,
    )
    _assert(
        "panel6_toy_weight",
        cairo_toy_font_face_get_weight(tf).value
        == _cairo_font_weight.CAIRO_FONT_WEIGHT_NORMAL.value,
    )
    _assert(
        "panel6_toy_family_nonnull",
        cairo_toy_font_face_get_family(tf)
        != UnsafePointer[Int8, ImmutExternalOrigin](),
    )
    cairo_font_face_destroy(tf)

    var hello = CStringSlice("Hello Cairo\0")
    cairo_set_source_rgb(cr, 0.0, 0.0, 0.0)
    cairo_move_to(cr, 12.0, 60.0)
    cairo_show_text(
        cr, rebind[UnsafePointer[Int8, ImmutExternalOrigin]](hello.unsafe_ptr())
    )
    _ok("panel6_show_text", cairo_status(cr))
    cairo_move_to(cr, 12.0, 120.0)
    cairo_text_path(
        cr, rebind[UnsafePointer[Int8, ImmutExternalOrigin]](hello.unsafe_ptr())
    )
    _ok("panel6_text_path", cairo_status(cr))
    cairo_new_path(cr)
    var glyphs = cairo_glyph_allocate(4)
    _assert(
        "panel6_glyph_alloc_nonnull",
        glyphs != UnsafePointer[cairo_glyph_t, MutExternalOrigin](),
    )
    cairo_glyph_free(glyphs)
    cairo_restore(cr)

    _draw_panel_border(cr, 20.0, 420.0, 300.0, 180.0)
    cairo_save(cr)
    cairo_translate(cr, 20.0, 420.0)
    var rec = cairo_recording_surface_create(
        materialize[_cairo_content.CAIRO_CONTENT_COLOR_ALPHA](),
        UnsafePointer[_cairo_rectangle, ImmutExternalOrigin](),
    )
    _ok("panel7_recording_surface_create", cairo_surface_status(rec))
    var rec_cr = cairo_create(rec)
    cairo_set_source_rgb(rec_cr, 0.95, 0.8, 0.1)
    cairo_rectangle(rec_cr, 10.0, 10.0, 180.0, 120.0)
    cairo_fill(rec_cr)
    _ok("panel7_recording_fill", cairo_status(rec_cr))
    cairo_destroy(rec_cr)
    cairo_set_source_surface(cr, rec, 20.0, 20.0)
    cairo_paint_with_alpha(cr, 0.85)
    _ok("panel7_set_source_surface", cairo_status(cr))
    cairo_surface_destroy(rec)
    cairo_restore(cr)

    print("composite_scene|PASS")


def run_non_visual_object_checks() raises:
    var opts = cairo_font_options_create()
    _ok("font_options_create", cairo_font_options_status(opts))
    var opts2 = cairo_font_options_copy(
        rebind[UnsafePointer[cairo_font_options_t, ImmutExternalOrigin]](opts)
    )
    _ok("font_options_copy", cairo_font_options_status(opts2))
    cairo_font_options_merge(
        opts,
        rebind[UnsafePointer[cairo_font_options_t, ImmutExternalOrigin]](opts2),
    )
    _assert(
        "font_options_equal",
        cairo_font_options_equal(
            rebind[UnsafePointer[cairo_font_options_t, ImmutExternalOrigin]](
                opts
            ),
            rebind[UnsafePointer[cairo_font_options_t, ImmutExternalOrigin]](
                opts2
            ),
        )
        != 0,
    )
    _assert(
        "font_options_hash_stable",
        cairo_font_options_hash(
            rebind[UnsafePointer[cairo_font_options_t, ImmutExternalOrigin]](
                opts
            )
        )
        == 0,
    )
    cairo_font_options_set_antialias(
        opts, materialize[_cairo_antialias.CAIRO_ANTIALIAS_GRAY]()
    )
    _assert(
        "font_options_antialias",
        cairo_font_options_get_antialias(opts).value
        == _cairo_antialias.CAIRO_ANTIALIAS_GRAY.value,
    )
    cairo_font_options_set_subpixel_order(
        opts, materialize[_cairo_subpixel_order.CAIRO_SUBPIXEL_ORDER_RGB]()
    )
    _assert(
        "font_options_subpixel",
        cairo_font_options_get_subpixel_order(opts).value
        == _cairo_subpixel_order.CAIRO_SUBPIXEL_ORDER_RGB.value,
    )
    cairo_font_options_set_hint_style(
        opts, materialize[_cairo_hint_style.CAIRO_HINT_STYLE_FULL]()
    )
    _assert(
        "font_options_hint_style",
        cairo_font_options_get_hint_style(opts).value
        == _cairo_hint_style.CAIRO_HINT_STYLE_FULL.value,
    )
    cairo_font_options_set_hint_metrics(
        opts, materialize[_cairo_hint_metrics.CAIRO_HINT_METRICS_ON]()
    )
    _assert(
        "font_options_hint_metrics",
        cairo_font_options_get_hint_metrics(opts).value
        == _cairo_hint_metrics.CAIRO_HINT_METRICS_ON.value,
    )
    cairo_font_options_destroy(opts2)
    cairo_font_options_destroy(opts)

    var rect_storage = alloc[_cairo_rectangle_int](1)
    rect_storage[0] = _cairo_rectangle_int(10, 10, 60, 60)
    var reg = cairo_region_create_rectangle(rect_storage)
    rect_storage.free()
    _ok("region_create_rectangle", cairo_region_status(reg))
    _assert(
        "region_not_empty",
        cairo_region_is_empty(reg) == 0,
    )
    _assert(
        "region_contains_inside",
        cairo_region_contains_point(reg, 30, 30) != 0,
    )
    _assert(
        "region_contains_outside",
        cairo_region_contains_point(reg,2,2)== 0,
    )
    _assert(
        "region_rects_nonneg",
        cairo_region_num_rectangles(reg) >= 0,
    )

    var extents = alloc[_cairo_rectangle_int](1)
    cairo_region_get_extents(reg,extents)
    extents.free()
    var reg2 = cairo_region_copy(reg)
    _assert(
        "region_equal_after_copy",
        cairo_region_equal(reg,reg2)!= 0,
    )
    cairo_region_translate(reg2, 5, 5)
    _assert(
        "region_not_equal_after_translate",
        cairo_region_equal(reg,reg2)== 0,
    )
    cairo_region_destroy(reg2)
    var reg_ref = cairo_region_reference(reg)
    cairo_region_destroy(reg_ref)

    var empty = cairo_region_create()
    _ok("region_create_empty", cairo_region_status(empty))
    _assert(
        "region_empty_is_empty",
        cairo_region_is_empty(empty)!= 0,
    )
    cairo_region_destroy(empty)
    cairo_region_destroy(reg)
    print("non_visual_checks|PASS")


def run_png_roundtrip_from_composite(
    surface: UnsafePointer[cairo_surface_t, MutExternalOrigin]
) raises:
    var out_path = CStringSlice("/tmp/mojo_bindgen_cairo_smoke_composite.png\0")
    _ok(
        "surface_write_to_png",
        cairo_surface_write_to_png(
            surface,
            rebind[UnsafePointer[Int8, ImmutExternalOrigin]](
                out_path.unsafe_ptr()
            ),
        ),
    )
    var loaded = cairo_image_surface_create_from_png(
        rebind[UnsafePointer[Int8, ImmutExternalOrigin]](out_path.unsafe_ptr())
    )
    _ok("png_load", cairo_surface_status(loaded))
    _assert("png_width", cairo_image_surface_get_width(loaded) == SCENE_W)
    _assert("png_height", cairo_image_surface_get_height(loaded) == SCENE_H)
    cairo_surface_destroy(loaded)
    print("png_roundtrip|PASS")


def run_debug_reset() raises:
    cairo_debug_reset_static_data()
    print("debug_reset_static_data|ok")


def main() raises:
    print("=== Cairo bindgen compact composite smoke test ===")
    run_metadata_and_lifecycle_checks()

    var surface = cairo_image_surface_create(
        materialize[_cairo_format.CAIRO_FORMAT_ARGB32](), SCENE_W, SCENE_H
    )
    _ok("composite_surface_create", cairo_surface_status(surface))
    var cr = cairo_create(surface)
    _ok("composite_context_create", cairo_status(cr))

    draw_composite_scene(cr)
    run_non_visual_object_checks()
    run_png_roundtrip_from_composite(surface)

    cairo_destroy(cr)
    cairo_surface_destroy(surface)
    run_debug_reset()

    print("")
    print("=== ALL TESTS PASSED ===")
