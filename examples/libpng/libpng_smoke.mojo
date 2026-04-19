# Cairo-style composable smoke for external-link libpng bindings.
# Requires libpng_bindings.mojo from generate.sh.
import libpng_bindings as png
from std.memory import alloc

comptime IMAGE_W = 2
comptime IMAGE_H = 2
comptime CHANNELS = 4
comptime PIXEL_BYTES = IMAGE_W * IMAGE_H * CHANNELS


def _assert(label: String, cond: Bool) raises:
    if not cond:
        raise Error("ASSERTION FAILED: " + label)
    print(label + "|ok")


def _cstr(s: StaticString) -> UnsafePointer[Int8, ImmutExternalOrigin]:
    return rebind[UnsafePointer[Int8, ImmutExternalOrigin]](s.unsafe_ptr())


def _cstr_mut(s: StaticString) -> UnsafePointer[Int8, MutExternalOrigin]:
    return rebind[UnsafePointer[Int8, MutExternalOrigin]](s.unsafe_ptr())


def run_version_checks() raises:
    var access_version = png.png_access_version_number()
    _assert("libpng.version_positive", access_version > 0)
    _assert("libpng.version_matches_header", Int32(access_version) == png.PNG_LIBPNG_VER)
    print("libpng.version_number|", access_version)


def run_write_roundtrip_checks() raises:
    var pixels = alloc[UInt8](PIXEL_BYTES)

    # BGRA, four pixels, deterministic test pattern.
    pixels[0] = 0
    pixels[1] = 0
    pixels[2] = 255
    # Make pixel0's alpha 0 so later alpha-removal/compositing checks
    # are deterministic.
    pixels[3] = 0
    pixels[4] = 0
    pixels[5] = 255
    pixels[6] = 0
    pixels[7] = 255
    pixels[8] = 255
    pixels[9] = 0
    pixels[10] = 0
    pixels[11] = 255
    pixels[12] = 255
    pixels[13] = 255
    pixels[14] = 255
    pixels[15] = 255

    var image_write = alloc[png.png_image](1)
    image_write[0] = png.png_image(
        opaque=UnsafePointer[png.png_control, MutExternalOrigin](),
        version=UInt32(png.PNG_IMAGE_VERSION),
        width=UInt32(IMAGE_W),
        height=UInt32(IMAGE_H),
        format=UInt32(png.PNG_FORMAT_BGRA),
        flags=0,
        colormap_entries=0,
        warning_or_error=0,
        message=InlineArray[Int8, 64](uninitialized=True),
    )
    var png_path = _cstr("/tmp/mojo_bindgen_libpng_smoke.png")
    var write_ok = png.png_image_write_to_file(
        image_write,
        png_path,
        0,
        rebind[ImmutOpaquePointer[ImmutExternalOrigin]](pixels),
        IMAGE_W * CHANNELS,
        ImmutOpaquePointer[ImmutExternalOrigin](),
    )
    _assert("libpng.write_to_file", write_ok != 0)

    var image_read = alloc[png.png_image](1)
    image_read[0] = png.png_image(
        opaque=UnsafePointer[png.png_control, MutExternalOrigin](),
        version=UInt32(png.PNG_IMAGE_VERSION),
        width=0,
        height=0,
        format=0,
        flags=0,
        colormap_entries=0,
        warning_or_error=0,
        message=InlineArray[Int8, 64](uninitialized=True),
    )
    var begin_ok = png.png_image_begin_read_from_file(image_read, png_path)
    _assert("libpng.begin_read_from_file", begin_ok != 0)
    _assert("libpng.read_width", image_read[0].width == UInt32(IMAGE_W))
    _assert("libpng.read_height", image_read[0].height == UInt32(IMAGE_H))

    image_read[0].format = UInt32(png.PNG_FORMAT_BGRA)
    var out_pixels = alloc[UInt8](PIXEL_BYTES)
    var finish_ok = png.png_image_finish_read(
        image_read,
        png.png_const_colorp(),
        rebind[MutOpaquePointer[MutExternalOrigin]](out_pixels),
        IMAGE_W * CHANNELS,
        MutOpaquePointer[MutExternalOrigin](),
    )
    _assert("libpng.finish_read", finish_ok != 0)
    _assert("libpng.pixel_roundtrip_0", out_pixels[0] == pixels[0])
    _assert("libpng.pixel_roundtrip_3", out_pixels[3] == pixels[3])
    _assert("libpng.pixel_roundtrip_15", out_pixels[15] == pixels[15])

    png.png_image_free(image_write)
    png.png_image_free(image_read)
    print("libpng.file_roundtrip_ok|", 1)


def run_memory_roundtrip_checks() raises:
    var pixels = alloc[UInt8](PIXEL_BYTES)

    # BGRA, four pixels, deterministic test pattern.
    pixels[0] = 0
    pixels[1] = 0
    pixels[2] = 255
    pixels[3] = 0
    pixels[4] = 0
    pixels[5] = 255
    pixels[6] = 0
    pixels[7] = 255
    pixels[8] = 255
    pixels[9] = 0
    pixels[10] = 0
    pixels[11] = 255
    pixels[12] = 255
    pixels[13] = 255
    pixels[14] = 255
    pixels[15] = 255

    # Build a writer-side png_image matching run_write_roundtrip_checks().
    var image_write = alloc[png.png_image](1)
    image_write[0] = png.png_image(
        opaque=UnsafePointer[png.png_control, MutExternalOrigin](),
        version=UInt32(png.PNG_IMAGE_VERSION),
        width=UInt32(IMAGE_W),
        height=UInt32(IMAGE_H),
        format=UInt32(png.PNG_FORMAT_BGRA),
        flags=0,
        colormap_entries=0,
        warning_or_error=0,
        message=InlineArray[Int8, 64](uninitialized=True),
    )

    # Exercise png_image_write_to_memory with both a NULL memory pointer
    # (size query) and a real memory buffer (actual write).
    var memory_bytes_out = alloc[UInt64](1)
    var write_size_ok = png.png_image_write_to_memory(
        image_write,
        MutOpaquePointer[MutExternalOrigin](),
        memory_bytes_out,
        0,
        rebind[ImmutOpaquePointer[ImmutExternalOrigin]](pixels),
        IMAGE_W * CHANNELS,
        ImmutOpaquePointer[ImmutExternalOrigin](),
    )
    _assert("libpng.write_to_memory_size", write_size_ok != 0)
    _assert("libpng.write_to_memory_size_nonzero", memory_bytes_out[0] > 0)

    var png_bytes = alloc[UInt8](Int(memory_bytes_out[0]))
    var write_ok = png.png_image_write_to_memory(
        image_write,
        rebind[MutOpaquePointer[MutExternalOrigin]](png_bytes),
        memory_bytes_out,
        0,
        rebind[ImmutOpaquePointer[ImmutExternalOrigin]](pixels),
        IMAGE_W * CHANNELS,
        ImmutOpaquePointer[ImmutExternalOrigin](),
    )
    _assert("libpng.write_to_memory", write_ok != 0)

    var image_read = alloc[png.png_image](1)
    image_read[0] = png.png_image(
        opaque=UnsafePointer[png.png_control, MutExternalOrigin](),
        version=UInt32(png.PNG_IMAGE_VERSION),
        width=0,
        height=0,
        format=0,
        flags=0,
        colormap_entries=0,
        warning_or_error=0,
        message=InlineArray[Int8, 64](uninitialized=True),
    )

    var begin_ok = png.png_image_begin_read_from_memory(
        image_read,
        rebind[ImmutOpaquePointer[ImmutExternalOrigin]](png_bytes),
        memory_bytes_out[0],
    )
    _assert("libpng.begin_read_from_memory", begin_ok != 0)
    image_read[0].format = UInt32(png.PNG_FORMAT_BGRA)

    var out_pixels = alloc[UInt8](PIXEL_BYTES)
    var finish_ok = png.png_image_finish_read(
        image_read,
        png.png_const_colorp(),
        rebind[MutOpaquePointer[MutExternalOrigin]](out_pixels),
        IMAGE_W * CHANNELS,
        MutOpaquePointer[MutExternalOrigin](),
    )
    _assert("libpng.finish_read_memory", finish_ok != 0)
    _assert("libpng.pixel_roundtrip_mem_0", out_pixels[0] == pixels[0])
    _assert("libpng.pixel_roundtrip_mem_3", out_pixels[3] == pixels[3])
    _assert("libpng.pixel_roundtrip_mem_15", out_pixels[15] == pixels[15])

    png.png_image_free(image_write)
    png.png_image_free(image_read)
    print("libpng.memory_roundtrip_ok|", 1)


def run_alpha_removal_compositing_checks() raises:
    # Re-read the file produced in run_write_roundtrip_checks() and request
    # RGB output (no alpha). Then confirm compositing with a deterministic
    # background color.
    var image_read = alloc[png.png_image](1)
    image_read[0] = png.png_image(
        opaque=UnsafePointer[png.png_control, MutExternalOrigin](),
        version=UInt32(png.PNG_IMAGE_VERSION),
        width=0,
        height=0,
        format=0,
        flags=0,
        colormap_entries=0,
        warning_or_error=0,
        message=InlineArray[Int8, 64](uninitialized=True),
    )

    var png_path = _cstr("/tmp/mojo_bindgen_libpng_smoke.png")
    var begin_ok = png.png_image_begin_read_from_file(image_read, png_path)
    _assert("libpng.alpha_begin_read_from_file", begin_ok != 0)

    image_read[0].format = UInt32(png.PNG_FORMAT_RGB)

    var background = alloc[png.png_color_struct](1)
    background[0] = png.png_color_struct(red=7, green=11, blue=13)
    var background_ptr = rebind[
        UnsafePointer[png.png_color_struct, ImmutExternalOrigin]
    ](background)

    var out_rgb = alloc[UInt8](IMAGE_W * IMAGE_H * 3)
    var finish_ok = png.png_image_finish_read(
        image_read,
        background_ptr,
        rebind[MutOpaquePointer[MutExternalOrigin]](out_rgb),
        IMAGE_W * 3,
        MutOpaquePointer[MutExternalOrigin](),
    )
    _assert("libpng.alpha_finish_read", finish_ok != 0)

    # out_rgb layout for PNG_FORMAT_RGB is R,G,B per pixel (row-major).
    _assert("libpng.alpha_removed_pixel0_r", out_rgb[0] == 7)
    _assert("libpng.alpha_removed_pixel0_g", out_rgb[1] == 11)
    _assert("libpng.alpha_removed_pixel0_b", out_rgb[2] == 13)

    # Pixel1 is fully opaque in our BGRA test pattern.
    _assert("libpng.alpha_removed_pixel1_r", out_rgb[3] == 0)
    _assert("libpng.alpha_removed_pixel1_g", out_rgb[4] == 255)
    _assert("libpng.alpha_removed_pixel1_b", out_rgb[5] == 0)

    png.png_image_free(image_read)
    print("libpng.alpha_removal_composite_ok|", 1)


def run_transform_and_options_checks() raises:
    var png_ptr = png.png_create_write_struct(
        _cstr("1.6.43"),
        MutOpaquePointer[MutExternalOrigin](),
        UnsafePointer[png.png_error_ptr, MutExternalOrigin](),
        UnsafePointer[png.png_error_ptr, MutExternalOrigin](),
    )
    _assert("libpng.create_write_struct", png_ptr != png.png_structp())

    var info_ptr = png.png_create_info_struct(png_ptr)
    _assert("libpng.create_info_struct", info_ptr != png.png_infop())

    # Configure representative writer-side options.
    png.png_set_crc_action(png_ptr, png.PNG_CRC_WARN_USE, png.PNG_CRC_WARN_DISCARD)
    png.png_set_filter(png_ptr, png.PNG_FILTER_TYPE_BASE, png.PNG_ALL_FILTERS)
    png.png_set_compression_level(png_ptr, 6)
    png.png_set_compression_strategy(png_ptr, 0)
    png.png_set_flush(png_ptr, 2)
    png.png_set_text_compression_level(png_ptr, 6)

    png.png_set_IHDR(
        png_ptr,
        info_ptr,
        UInt32(IMAGE_W),
        UInt32(IMAGE_H),
        8,
        png.PNG_COLOR_TYPE_RGB_ALPHA,
        png.PNG_INTERLACE_NONE,
        png.PNG_COMPRESSION_TYPE_BASE,
        png.PNG_FILTER_TYPE_BASE,
    )
    png.png_set_pHYs(
        png_ptr,
        info_ptr,
        3780,
        3780,
        png.PNG_RESOLUTION_METER,
    )

    var text_entry = alloc[png.png_text_struct](1)
    text_entry[0] = png.png_text_struct(
        compression=png.PNG_TEXT_COMPRESSION_NONE,
        key=_cstr_mut("Comment"),
        text=_cstr_mut("mojo-bindgen-smoke"),
        text_length=18,
        itxt_length=0,
        lang=UnsafePointer[Int8, MutExternalOrigin](),
        lang_key=UnsafePointer[Int8, MutExternalOrigin](),
    )
    png.png_set_text(
        png_ptr,
        info_ptr,
        rebind[png.png_const_textp](text_entry),
        1,
    )

    var get_w = alloc[UInt32](1)
    var get_h = alloc[UInt32](1)
    var get_bd = alloc[Int32](1)
    var get_ct = alloc[Int32](1)
    var get_interlace = alloc[Int32](1)
    var get_compression = alloc[Int32](1)
    var get_filter = alloc[Int32](1)

    var ihdr_valid = png.png_get_IHDR(
        png_ptr,
        info_ptr,
        get_w,
        get_h,
        get_bd,
        get_ct,
        get_interlace,
        get_compression,
        get_filter,
    )
    _assert("libpng.get_ihdr_success", ihdr_valid != 0)
    _assert("libpng.ihdr_width", get_w[0] == UInt32(IMAGE_W))
    _assert("libpng.ihdr_height", get_h[0] == UInt32(IMAGE_H))
    _assert("libpng.ihdr_bit_depth", get_bd[0] == 8)
    _assert("libpng.ihdr_color_type", get_ct[0] == png.PNG_COLOR_TYPE_RGB_ALPHA)

    var res_x = alloc[UInt32](1)
    var res_y = alloc[UInt32](1)
    var unit_type = alloc[Int32](1)
    var phys_valid = png.png_get_pHYs(png_ptr, info_ptr, res_x, res_y, unit_type)
    _assert("libpng.get_phys_valid", phys_valid != 0)
    _assert("libpng.get_phys_x", res_x[0] == 3780)
    _assert("libpng.get_phys_y", res_y[0] == 3780)
    _assert("libpng.get_phys_unit", unit_type[0] == png.PNG_RESOLUTION_METER)

    var out_text = alloc[png.png_textp](1)
    var out_count = alloc[Int32](1)
    var text_count = png.png_get_text(png_ptr, info_ptr, out_text, out_count)
    _assert("libpng.get_text_count", text_count >= 1)
    _assert("libpng.get_text_num", out_count[0] >= 1)

    var png_ptr_ptr = alloc[png.png_structp](1)
    var info_ptr_ptr = alloc[png.png_infop](1)
    png_ptr_ptr[0] = png_ptr
    info_ptr_ptr[0] = info_ptr
    png.png_destroy_write_struct(png_ptr_ptr, info_ptr_ptr)
    print("libpng.transform_config_ok|", 1)


def run_lightweight_struct_api_checks() raises:
    var palette = alloc[png.png_color_struct](256)
    png.png_build_grayscale_palette(8, palette)
    _assert("libpng.palette_first_black", palette[0].red == 0)
    _assert("libpng.palette_last_white", palette[255].red == 255)

    var sig = alloc[UInt8](8)
    sig[0] = 137
    sig[1] = 80
    sig[2] = 78
    sig[3] = 71
    sig[4] = 13
    sig[5] = 10
    sig[6] = 26
    sig[7] = 10
    var sig_ok = png.png_sig_cmp(
        rebind[UnsafePointer[UInt8, ImmutExternalOrigin]](sig),
        0,
        8,
    )
    _assert("libpng.sig_cmp_valid", sig_ok == 0)
    sig[1] = 81
    var sig_bad = png.png_sig_cmp(
        rebind[UnsafePointer[UInt8, ImmutExternalOrigin]](sig),
        0,
        8,
    )
    _assert("libpng.sig_cmp_invalid", sig_bad != 0)
    print("libpng.struct_api_ok|", 1)


def main() raises:
    run_version_checks()
    run_write_roundtrip_checks()
    run_memory_roundtrip_checks()
    run_alpha_removal_compositing_checks()
    run_transform_and_options_checks()
    run_lightweight_struct_api_checks()
