# Cairo-style composable smoke for external-link libpng bindings.
# Requires libpng_bindings.mojo from generate.sh.
import libpng_bindings as png
from std.memory.alloc import alloc, Layout
from std.ffi import c_uint, c_char

comptime IMAGE_W = 2
comptime IMAGE_H = 2
comptime CHANNELS = 4
comptime PIXEL_BYTES = IMAGE_W * IMAGE_H * CHANNELS


def _assert(label: String, cond: Bool) raises:
    if not cond:
        raise Error("ASSERTION FAILED: " + label)
    print(label + "|ok")


def _cstr(s: StaticString) -> Pointer[c_char, ImmUntrackedOrigin]:
    return rebind[Pointer[c_char, ImmUntrackedOrigin]](s.unsafe_ptr())


def _cstr_mut(s: StaticString) -> Pointer[c_char, MutUntrackedOrigin]:
    return rebind[Pointer[c_char, MutUntrackedOrigin]](s.unsafe_ptr())


def _ignore_png_message(png_ptr: png.png_structp, msg: png.png_const_charp) abi("C"):
    pass


def run_version_checks() raises:
    var access_version = png.png_access_version_number()
    _assert("libpng.version_positive", access_version > 0)
    _assert(
        "libpng.version_matches_header",
        access_version == UInt32(png.PNG_LIBPNG_VER),
    )
    print("libpng.version_number|", access_version)


def run_write_roundtrip_checks() raises:
    var pixels = alloc(Layout[UInt8](count=PIXEL_BYTES)).unsafe_leak()

    # BGRA, four pixels, deterministic test pattern.
    pixels[unsafe_offset=0] = 0
    pixels[unsafe_offset=1] = 0
    pixels[unsafe_offset=2] = 255
    # Make pixel0's alpha 0 so later alpha-removal/compositing checks
    # are deterministic.
    pixels[unsafe_offset=3] = 0
    pixels[unsafe_offset=4] = 0
    pixels[unsafe_offset=5] = 255
    pixels[unsafe_offset=6] = 0
    pixels[unsafe_offset=7] = 255
    pixels[unsafe_offset=8] = 255
    pixels[unsafe_offset=9] = 0
    pixels[unsafe_offset=10] = 0
    pixels[unsafe_offset=11] = 255
    pixels[unsafe_offset=12] = 255
    pixels[unsafe_offset=13] = 255
    pixels[unsafe_offset=14] = 255
    pixels[unsafe_offset=15] = 255

    var image_write = alloc(Layout[png.png_image](count=1)).unsafe_leak()
    image_write[unsafe_offset=0] = png.png_image(
        opaque=Optional[Pointer[png.png_control, MutUntrackedOrigin]](),
        version=c_uint(png.PNG_IMAGE_VERSION),
        width=c_uint(IMAGE_W),
        height=c_uint(IMAGE_H),
        format=c_uint(png.PNG_FORMAT_BGRA),
        flags=0,
        colormap_entries=0,
        warning_or_error=0,
        message=Array[c_char, 64](uninitialized=True),
    )
    var png_path = _cstr("/tmp/mojo_bindgen_libpng_smoke.png")
    var write_ok = png.png_image_write_to_file(
        image_write,
        png_path,
        0,
        rebind[OpaquePointer[mut=False, ImmUntrackedOrigin]](pixels),
        IMAGE_W * CHANNELS,
        Optional[OpaquePointer[mut=False, ImmUntrackedOrigin]](),
    )
    _assert("libpng.write_to_file", write_ok != 0)

    var image_read = alloc(Layout[png.png_image](count=1)).unsafe_leak()
    image_read[unsafe_offset=0] = png.png_image(
        opaque=Optional[Pointer[png.png_control, MutUntrackedOrigin]](),
        version=c_uint(png.PNG_IMAGE_VERSION),
        width=0,
        height=0,
        format=0,
        flags=0,
        colormap_entries=0,
        warning_or_error=0,
        message=Array[c_char, 64](uninitialized=True),
    )
    var begin_ok = png.png_image_begin_read_from_file(image_read, png_path)
    _assert("libpng.begin_read_from_file", begin_ok != 0)
    _assert("libpng.read_width", image_read[unsafe_offset=0].width == UInt32(IMAGE_W))
    _assert("libpng.read_height", image_read[unsafe_offset=0].height == UInt32(IMAGE_H))

    image_read[unsafe_offset=0].format = UInt32(png.PNG_FORMAT_BGRA)
    var out_pixels = alloc(Layout[UInt8](count=PIXEL_BYTES)).unsafe_leak()
    var finish_ok = png.png_image_finish_read(
        image_read,
        png.png_const_colorp(),
        rebind[OpaquePointer[mut=True, MutUntrackedOrigin]](out_pixels),
        IMAGE_W * CHANNELS,
        Optional[OpaquePointer[mut=True, MutUntrackedOrigin]](),
    )
    _assert("libpng.finish_read", finish_ok != 0)
    _assert("libpng.pixel_roundtrip_0", out_pixels[unsafe_offset=0] == pixels[unsafe_offset=0])
    _assert("libpng.pixel_roundtrip_3", out_pixels[unsafe_offset=3] == pixels[unsafe_offset=3])
    _assert("libpng.pixel_roundtrip_15", out_pixels[unsafe_offset=15] == pixels[unsafe_offset=15])

    png.png_image_free(image_write)
    png.png_image_free(image_read)
    print("libpng.file_roundtrip_ok|", 1)


def run_memory_roundtrip_checks() raises:
    var pixels = alloc(Layout[UInt8](count=PIXEL_BYTES)).unsafe_leak()

    # BGRA, four pixels, deterministic test pattern.
    pixels[unsafe_offset=0] = 0
    pixels[unsafe_offset=1] = 0
    pixels[unsafe_offset=2] = 255
    pixels[unsafe_offset=3] = 0
    pixels[unsafe_offset=4] = 0
    pixels[unsafe_offset=5] = 255
    pixels[unsafe_offset=6] = 0
    pixels[unsafe_offset=7] = 255
    pixels[unsafe_offset=8] = 255
    pixels[unsafe_offset=9] = 0
    pixels[unsafe_offset=10] = 0
    pixels[unsafe_offset=11] = 255
    pixels[unsafe_offset=12] = 255
    pixels[unsafe_offset=13] = 255
    pixels[unsafe_offset=14] = 255
    pixels[unsafe_offset=15] = 255

    # Build a writer-side png_image matching run_write_roundtrip_checks().
    var image_write = alloc(Layout[png.png_image](count=1)).unsafe_leak()
    image_write[unsafe_offset=0] = png.png_image(
        opaque=Optional[Pointer[png.png_control, MutUntrackedOrigin]](),
        version=c_uint(png.PNG_IMAGE_VERSION),
        width=c_uint(IMAGE_W),
        height=c_uint(IMAGE_H),
        format=c_uint(png.PNG_FORMAT_BGRA),
        flags=0,
        colormap_entries=0,
        warning_or_error=0,
        message=Array[c_char, 64](uninitialized=True),
    )

    # Exercise png_image_write_to_memory with both a NULL memory pointer
    # (size query) and a real memory buffer (actual write).
    var memory_bytes_out = alloc(Layout[png.png_alloc_size_t](count=1)).unsafe_leak()
    var write_size_ok = png.png_image_write_to_memory(
        image_write,
        Optional[OpaquePointer[mut=True, MutUntrackedOrigin]](),
        memory_bytes_out,
        0,
        rebind[OpaquePointer[mut=False, ImmUntrackedOrigin]](pixels),
        IMAGE_W * CHANNELS,
        Optional[OpaquePointer[mut=False, ImmUntrackedOrigin]](),
    )
    _assert("libpng.write_to_memory_size", write_size_ok != 0)
    _assert("libpng.write_to_memory_size_nonzero", memory_bytes_out[unsafe_offset=0] > 0)

    var png_bytes = alloc(Layout[UInt8](count=Int(memory_bytes_out[unsafe_offset=0]))).unsafe_leak()
    var write_ok = png.png_image_write_to_memory(
        image_write,
        rebind[OpaquePointer[mut=True, MutUntrackedOrigin]](png_bytes),
        memory_bytes_out,
        0,
        rebind[OpaquePointer[mut=False, ImmUntrackedOrigin]](pixels),
        IMAGE_W * CHANNELS,
        Optional[OpaquePointer[mut=False, ImmUntrackedOrigin]](),
    )
    _assert("libpng.write_to_memory", write_ok != 0)

    var image_read = alloc(Layout[png.png_image](count=1)).unsafe_leak()
    image_read[unsafe_offset=0] = png.png_image(
        opaque=Optional[Pointer[png.png_control, MutUntrackedOrigin]](),
        version=UInt32(png.PNG_IMAGE_VERSION),
        width=0,
        height=0,
        format=0,
        flags=0,
        colormap_entries=0,
        warning_or_error=0,
        message=Array[c_char, 64](uninitialized=True),
    )

    var begin_ok = png.png_image_begin_read_from_memory(
        image_read,
        rebind[OpaquePointer[mut=False, ImmUntrackedOrigin]](png_bytes),
        UInt(memory_bytes_out[unsafe_offset=0]),
    )
    _assert("libpng.begin_read_from_memory", begin_ok != 0)
    image_read[unsafe_offset=0].format = UInt32(png.PNG_FORMAT_BGRA)

    var out_pixels = alloc(Layout[UInt8](count=PIXEL_BYTES)).unsafe_leak()
    var finish_ok = png.png_image_finish_read(
        image_read,
        png.png_const_colorp(),
        rebind[OpaquePointer[mut=True, MutUntrackedOrigin]](out_pixels),
        IMAGE_W * CHANNELS,
        Optional[OpaquePointer[mut=True, MutUntrackedOrigin]](),
    )
    _assert("libpng.finish_read_memory", finish_ok != 0)
    _assert("libpng.pixel_roundtrip_mem_0", out_pixels[unsafe_offset=0] == pixels[unsafe_offset=0])
    _assert("libpng.pixel_roundtrip_mem_3", out_pixels[unsafe_offset=3] == pixels[unsafe_offset=3])
    _assert(
        "libpng.pixel_roundtrip_mem_15", out_pixels[unsafe_offset=15] == pixels[unsafe_offset=15]
    )

    png.png_image_free(image_write)
    png.png_image_free(image_read)
    print("libpng.memory_roundtrip_ok|", 1)


def run_alpha_removal_compositing_checks() raises:
    # Re-read the file produced in run_write_roundtrip_checks() and request
    # RGB output (no alpha). Then confirm compositing with a deterministic
    # background color.
    var image_read = alloc(Layout[png.png_image](count=1)).unsafe_leak()
    image_read[unsafe_offset=0] = png.png_image(
        opaque=Optional[Pointer[png.png_control, MutUntrackedOrigin]](),
        version=UInt32(png.PNG_IMAGE_VERSION),
        width=0,
        height=0,
        format=0,
        flags=0,
        colormap_entries=0,
        warning_or_error=0,
        message=Array[c_char, 64](uninitialized=True),
    )

    var png_path = _cstr("/tmp/mojo_bindgen_libpng_smoke.png")
    var begin_ok = png.png_image_begin_read_from_file(image_read, png_path)
    _assert("libpng.alpha_begin_read_from_file", begin_ok != 0)

    image_read[unsafe_offset=0].format = UInt32(png.PNG_FORMAT_RGB)

    var background = alloc(Layout[png.png_color_struct](count=1)).unsafe_leak()
    background[unsafe_offset=0] = png.png_color_struct(red=7, green=11, blue=13)
    var background_ptr = rebind[Pointer[png.png_color_struct, ImmUntrackedOrigin]](background)

    var out_rgb = alloc(Layout[UInt8](count=IMAGE_W * IMAGE_H * 3)).unsafe_leak()
    var finish_ok = png.png_image_finish_read(
        image_read,
        background_ptr,
        rebind[OpaquePointer[mut=True, MutUntrackedOrigin]](out_rgb),
        IMAGE_W * 3,
        Optional[OpaquePointer[mut=True, MutUntrackedOrigin]](),
    )
    _assert("libpng.alpha_finish_read", finish_ok != 0)

    # out_rgb layout for PNG_FORMAT_RGB is R,G,B per pixel (row-major).
    _assert("libpng.alpha_removed_pixel0_r", out_rgb[unsafe_offset=0] == 7)
    _assert("libpng.alpha_removed_pixel0_g", out_rgb[unsafe_offset=1] == 11)
    _assert("libpng.alpha_removed_pixel0_b", out_rgb[unsafe_offset=2] == 13)

    # Pixel1 is fully opaque in our BGRA test pattern.
    _assert("libpng.alpha_removed_pixel1_r", out_rgb[unsafe_offset=3] == 0)
    _assert("libpng.alpha_removed_pixel1_g", out_rgb[unsafe_offset=4] == 255)
    _assert("libpng.alpha_removed_pixel1_b", out_rgb[unsafe_offset=5] == 0)

    png.png_image_free(image_read)
    print("libpng.alpha_removal_composite_ok|", 1)


def run_transform_and_options_checks() raises:
    var png_ptr = png.png_create_write_struct(
        _cstr("1.6.43"),
        Optional[OpaquePointer[mut=True, MutUntrackedOrigin]](),
        _ignore_png_message,
        _ignore_png_message,
    )
    _assert("libpng.create_write_struct", png_ptr != png.png_structp())

    var info_ptr = png.png_create_info_struct(rebind[png.png_const_structrp](png_ptr))
    _assert("libpng.create_info_struct", info_ptr != png.png_infop())
    var png_const_ptr = rebind[png.png_const_structrp](png_ptr)
    var info_const_ptr = rebind[png.png_const_inforp](info_ptr)

    # Configure representative writer-side options.
    png.png_set_crc_action(png_ptr, Int32(png.PNG_CRC_WARN_USE), Int32(png.PNG_CRC_WARN_DISCARD))
    png.png_set_filter(png_ptr, Int32(png.PNG_FILTER_TYPE_BASE), Int32(png.PNG_ALL_FILTERS))
    png.png_set_compression_level(png_ptr, 6)
    png.png_set_compression_strategy(png_ptr, 0)
    png.png_set_flush(png_ptr, 2)
    png.png_set_text_compression_level(png_ptr, 6)

    png.png_set_IHDR(
        png_const_ptr,
        info_ptr,
        UInt32(IMAGE_W),
        UInt32(IMAGE_H),
        8,
        Int32(png.PNG_COLOR_TYPE_RGB_ALPHA),
        Int32(png.PNG_INTERLACE_NONE),
        Int32(png.PNG_COMPRESSION_TYPE_BASE),
        Int32(png.PNG_FILTER_TYPE_BASE),
    )
    png.png_set_pHYs(
        png_const_ptr,
        info_ptr,
        3780,
        3780,
        Int32(png.PNG_RESOLUTION_METER),
    )

    var text_entry = alloc(Layout[png.png_text_struct](count=1)).unsafe_leak()
    text_entry[unsafe_offset=0] = png.png_text_struct(
        compression=Int32(png.PNG_TEXT_COMPRESSION_NONE),
        key=_cstr_mut("Comment"),
        text=_cstr_mut("mojo-bindgen-smoke"),
        text_length=18,
        itxt_length=0,
        lang=Optional[Pointer[c_char, MutUntrackedOrigin]](),
        lang_key=Optional[Pointer[c_char, MutUntrackedOrigin]](),
    )
    png.png_set_text(
        png_const_ptr,
        info_ptr,
        rebind[png.png_const_textp](
            Optional[Pointer[png.png_text_struct, MutUntrackedOrigin]](text_entry)
        ),
        1,
    )

    var get_w = alloc(Layout[UInt32](count=1)).unsafe_leak()
    var get_h = alloc(Layout[UInt32](count=1)).unsafe_leak()
    var get_bd = alloc(Layout[Int32](count=1)).unsafe_leak()
    var get_ct = alloc(Layout[Int32](count=1)).unsafe_leak()
    var get_interlace = alloc(Layout[Int32](count=1)).unsafe_leak()
    var get_compression = alloc(Layout[Int32](count=1)).unsafe_leak()
    var get_filter = alloc(Layout[Int32](count=1)).unsafe_leak()

    var ihdr_valid = png.png_get_IHDR(
        png_const_ptr,
        info_const_ptr,
        get_w,
        get_h,
        get_bd,
        get_ct,
        get_interlace,
        get_compression,
        get_filter,
    )
    _assert("libpng.get_ihdr_success", ihdr_valid != 0)
    _assert("libpng.ihdr_width", get_w[unsafe_offset=0] == UInt32(IMAGE_W))
    _assert("libpng.ihdr_height", get_h[unsafe_offset=0] == UInt32(IMAGE_H))
    _assert("libpng.ihdr_bit_depth", get_bd[unsafe_offset=0] == 8)
    _assert(
        "libpng.ihdr_color_type",
        get_ct[unsafe_offset=0] == Int32(png.PNG_COLOR_TYPE_RGB_ALPHA),
    )

    var res_x = alloc(Layout[UInt32](count=1)).unsafe_leak()
    var res_y = alloc(Layout[UInt32](count=1)).unsafe_leak()
    var unit_type = alloc(Layout[Int32](count=1)).unsafe_leak()
    var phys_valid = png.png_get_pHYs(png_const_ptr, info_const_ptr, res_x, res_y, unit_type)
    _assert("libpng.get_phys_valid", phys_valid != 0)
    _assert("libpng.get_phys_x", res_x[unsafe_offset=0] == 3780)
    _assert("libpng.get_phys_y", res_y[unsafe_offset=0] == 3780)
    _assert("libpng.get_phys_unit", unit_type[unsafe_offset=0] == Int32(png.PNG_RESOLUTION_METER))

    var out_text = alloc(Layout[png.png_textp](count=1)).unsafe_leak()
    var out_count = alloc(Layout[Int32](count=1)).unsafe_leak()
    var text_count = png.png_get_text(png_const_ptr, info_ptr, out_text, out_count)
    _assert("libpng.get_text_count", text_count >= 1)
    _assert("libpng.get_text_num", out_count[unsafe_offset=0] >= 1)

    var png_ptr_ptr = alloc(Layout[png.png_structp](count=1)).unsafe_leak()
    var info_ptr_ptr = alloc(Layout[png.png_infop](count=1)).unsafe_leak()
    png_ptr_ptr[unsafe_offset=0] = png_ptr
    info_ptr_ptr[unsafe_offset=0] = info_ptr
    png.png_destroy_write_struct(png_ptr_ptr, info_ptr_ptr)
    print("libpng.transform_config_ok|", 1)


def run_lightweight_struct_api_checks() raises:
    var palette = alloc(Layout[png.png_color_struct](count=256)).unsafe_leak()
    png.png_build_grayscale_palette(8, palette)
    _assert("libpng.palette_first_black", palette[unsafe_offset=0].red == 0)
    _assert("libpng.palette_last_white", palette[unsafe_offset=255].red == 255)

    var sig = alloc(Layout[UInt8](count=8)).unsafe_leak()
    sig[unsafe_offset=0] = 137
    sig[unsafe_offset=1] = 80
    sig[unsafe_offset=2] = 78
    sig[unsafe_offset=3] = 71
    sig[unsafe_offset=4] = 13
    sig[unsafe_offset=5] = 10
    sig[unsafe_offset=6] = 26
    sig[unsafe_offset=7] = 10
    var sig_ok = png.png_sig_cmp(
        rebind[Pointer[UInt8, ImmUntrackedOrigin]](sig),
        0,
        8,
    )
    _assert("libpng.sig_cmp_valid", sig_ok == 0)
    sig[unsafe_offset=1] = 81
    var sig_bad = png.png_sig_cmp(
        rebind[Pointer[UInt8, ImmUntrackedOrigin]](sig),
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
