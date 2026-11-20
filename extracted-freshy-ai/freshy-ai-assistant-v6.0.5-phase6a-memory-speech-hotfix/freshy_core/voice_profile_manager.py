from __future__ import annotations

import argparse

try:
    from human_tts_service import HumanVoiceProfileStore
except ImportError:
    from freshy_core.human_tts_service import HumanVoiceProfileStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage consented Freshy XTTS human voice profiles"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser("install", help="Install or replace a voice profile")
    install.add_argument("--id", required=True, dest="profile_id")
    install.add_argument("--label", required=True)
    install.add_argument(
        "--reference",
        required=True,
        action="append",
        help="Path to a clean consented WAV. Repeat for multiple reference clips.",
    )
    install.add_argument("--language", default="hi")
    install.add_argument("--description", default="Custom consented XTTS voice")

    subparsers.add_parser("list", help="List installed voice profiles")
    remove = subparsers.add_parser("remove", help="Remove an installed profile")
    remove.add_argument("--id", required=True, dest="profile_id")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    store = HumanVoiceProfileStore()
    if args.command == "install":
        profile = store.install_profile(
            profile_id=args.profile_id,
            label=args.label,
            reference_wavs=args.reference,
            language=args.language,
            description=args.description,
        )
        print(
            f"Installed XTTS profile: {profile.id} ({profile.label}), "
            f"references={len(profile.reference_wavs)}"
        )
        return 0
    if args.command == "list":
        profiles = store.list_profiles()
        if not profiles:
            print("No XTTS human voice profiles are installed.")
            return 0
        for profile in profiles:
            print(
                f"{profile.id}\t{profile.label}\t{profile.language}\t"
                f"references={len(profile.reference_wavs)}"
            )
        return 0
    if args.command == "remove":
        store.remove_profile(args.profile_id)
        print(f"Removed XTTS profile: {args.profile_id}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
