from ...ir import TargetABI


@fieldwise_init
struct TargetQueries(Copyable, Movable):
    var abi: TargetABI

    def default_char_is_unsigned(self) -> Optional[Bool]:
        if not self.abi.target_triple:
            return {}
        var triple = self.abi.target_triple.value().copy()
        return "linux" in triple and (
            triple.startswith("aarch64") or triple.startswith("arm") or triple.startswith("thumb")
        )
