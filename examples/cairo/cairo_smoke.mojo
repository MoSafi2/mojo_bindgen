# Smoke test for external_call Cairo bindings with runtime rendering round-trip.
from std.ffi import CStringSlice
from cairo_bindings import (
    _cairo_format,
    _cairo_status,
    cairo_create,
    cairo_destroy,
    cairo_image_surface_create,
    cairo_image_surface_create_from_png,
    cairo_image_surface_get_height,
    cairo_image_surface_get_width,
    cairo_line_to,
    cairo_move_to,
    cairo_paint,
    cairo_set_line_width,
    cairo_set_source_rgb,
    cairo_status,
    cairo_stroke,
    cairo_surface_destroy,
    cairo_surface_status,
    cairo_surface_write_to_png,
    cairo_version,
)


def _check_status(label: String, status: UInt32) raises:
    if status != _cairo_status.CAIRO_STATUS_SUCCESS.value:
        raise Error(label + " failed with cairo status " + String(status))


def main() raises:
    print("cairo.version|", cairo_version())
    var out_path = CStringSlice("/tmp/mojo_bindgen_cairo_smoke.png\0")

    var surface = cairo_image_surface_create(
        _cairo_format.CAIRO_FORMAT_ARGB32.value, 64, 64
    )
    _check_status("cairo_image_surface_create", cairo_surface_status(surface))

    var cr = cairo_create(surface)
    _check_status("cairo_create", cairo_status(cr))

    cairo_set_source_rgb(cr, 1.0, 1.0, 1.0)
    cairo_paint(cr)
    cairo_set_source_rgb(cr, 1.0, 0.0, 0.0)
    cairo_set_line_width(cr, 6.0)
    cairo_move_to(cr, 8.0, 8.0)
    cairo_line_to(cr, 56.0, 56.0)
    cairo_stroke(cr)
    _check_status("draw ops", cairo_status(cr))

    _check_status(
        "cairo_surface_write_to_png",
        cairo_surface_write_to_png(
            surface,
            rebind[UnsafePointer[Int8, ImmutExternalOrigin]](
                out_path.unsafe_ptr()
            ),
        ),
    )

    cairo_destroy(cr)
    cairo_surface_destroy(surface)

    var loaded = cairo_image_surface_create_from_png(
        rebind[UnsafePointer[Int8, ImmutExternalOrigin]](out_path.unsafe_ptr())
    )
    _check_status(
        "cairo_image_surface_create_from_png", cairo_surface_status(loaded)
    )
    if cairo_image_surface_get_width(loaded) != 64:
        cairo_surface_destroy(loaded)
        raise Error("loaded PNG width mismatch")
    if cairo_image_surface_get_height(loaded) != 64:
        cairo_surface_destroy(loaded)
        raise Error("loaded PNG height mismatch")
    cairo_surface_destroy(loaded)

    print("cairo.file_roundtrip_ok|", 1)
