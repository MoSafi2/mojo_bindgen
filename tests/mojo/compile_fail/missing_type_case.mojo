from mojo_bindgen.ir import CType


def incomplete(value: CType) -> Int:
    match value:
        case .void_type(_):
            return 0


def main():
    pass
