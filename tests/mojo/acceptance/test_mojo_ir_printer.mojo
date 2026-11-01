"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_render_struct_decl_preserves_trait_order_c97f6c2e5190() raises:
    check_case("test_mojo_ir_printer/c97f6c2e5190.json.gz")


def test_render_mojo_module_external_surface_with_synthesized_callback_aliases_4f0954f0f361() raises:
    check_case("test_mojo_ir_printer/4f0954f0f361.json.gz")


def test_render_bitfield_accessors_branch_on_target_endianness_comptime_251306d1878f() raises:
    check_case("test_mojo_ir_printer/251306d1878f.json.gz")


def test_render_callback_alias_uses_none_in_signature_position_43f49c2b4de9() raises:
    check_case("test_mojo_ir_printer/43f49c2b4de9.json.gz")


def test_render_struct_emits_flexible_tail_helpers_db64aa039fe4() raises:
    check_case("test_mojo_ir_printer/db64aa039fe4.json.gz")


def test_normalize_and_render_sizeof_imports_std_sys_info_ae0f3e38d170() raises:
    check_case("test_mojo_ir_printer/ae0f3e38d170.json.gz")


def test_normalize_mojo_module_makes_callback_hoisting_and_imports_explicit_efeb748b5593() raises:
    check_case("test_mojo_ir_printer/efeb748b5593.json.gz")


def test_normalize_mojo_module_coalesces_seeded_and_discovered_dependencies_5d551be97f7c() raises:
    check_case("test_mojo_ir_printer/5d551be97f7c.json.gz")


def test_render_mojo_module_uses_owned_dl_handle_library_path_hint_a87f41276b5e() raises:
    check_case("test_mojo_ir_printer/a87f41276b5e.json.gz")


def test_render_owned_dl_handle_sanitizes_library_path_env_var_5cc3c75ca1c0() raises:
    check_case("test_mojo_ir_printer/5cc3c75ca1c0.json.gz")


def test_render_owned_dl_handle_function_local_does_not_collide_with_parameters_fe20c2bc8d04() raises:
    check_case("test_mojo_ir_printer/fe20c2bc8d04.json.gz")


def test_render_mojo_module_emits_inline_directive_stub_comments_a4244b538689() raises:
    check_case("test_mojo_ir_printer/a4244b538689.json.gz")


def test_normalize_mojo_module_sets_align_decorator_before_printing_87f0f66956e2() raises:
    check_case("test_mojo_ir_printer/87f0f66956e2.json.gz")


def test_normalize_and_printer_keep_union_byte_fallback_without_unsafe_union_import_d2491febe2bb() raises:
    check_case("test_mojo_ir_printer/d2491febe2bb.json.gz")


def test_printer_uses_explicit_align_decorator_only_f3cea8fd6a4f() raises:
    check_case("test_mojo_ir_printer/f3cea8fd6a4f.json.gz")


def test_printer_renders_lowered_struct_layout_members_without_normalize_inference_353d71fa5986() raises:
    check_case("test_mojo_ir_printer/353d71fa5986.json.gz")


def test_rendered_mojo_module_compiles_with_mixed_decl_kinds_94196c4865d6() raises:
    check_case("test_mojo_ir_printer/94196c4865d6.json.gz")


def test_rendered_docstring_comments_escape_backslashes_for_mojo_00ad0d1a0c88() raises:
    check_case("test_mojo_ir_printer/00ad0d1a0c88.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
