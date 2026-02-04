import bencodepy
from pathlib import Path
import shutil
import sys
import argparse

BACKUP_SUFFIX = ".deluge-upload-resetter.bak"
BYTES_IN_GB = 1024 ** 3
DEFAULT_FILENAME = "torrents.fastresume"


def decode_value(val):
    """Recursively decode bytes for display purposes"""
    if isinstance(val, bytes):
        return val.decode(errors="ignore")
    elif isinstance(val, dict):
        return {decode_value(k): decode_value(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [decode_value(v) for v in val]
    else:
        return val


def reset_uploads(fastresume_path, single_mode=False):
    """Main logic for resetting upload statistics"""

    # Check file existence
    if not fastresume_path.exists():
        print(f"Error: File not found: {fastresume_path}")
        return False

    print(f"Using file: {fastresume_path}")
    if single_mode:
        print("Single file mode enabled\n")

    # Read and decode
    try:
        with open(fastresume_path, "rb") as f:
            raw = bencodepy.decode(f.read())
    except Exception as e:
        print(f"Error decoding file: {e}")
        return False

    torrents_to_reset = []

    for torrent_id, torrent_blob in raw.items():
        # Deluge uses double-level bencode
        if isinstance(torrent_blob, bytes):
            torrent_data = bencodepy.decode(torrent_blob)
        else:
            torrent_data = torrent_blob

        # Decode for display
        decoded = decode_value(torrent_data)
        name = decoded.get("name", "<unknown>")

        # Get total_uploaded
        uploaded_bytes = torrent_data.get(b"total_uploaded", 0)
        if isinstance(uploaded_bytes, int):
            uploaded_int = uploaded_bytes
            uploaded_bytes_len = (uploaded_int.bit_length() + 7) // 8 or 1
        elif isinstance(uploaded_bytes, bytes):
            uploaded_int = int.from_bytes(uploaded_bytes, "big")
            uploaded_bytes_len = len(uploaded_bytes)
        else:
            uploaded_int = 0
            uploaded_bytes_len = 1

        uploaded_gb = uploaded_int / BYTES_IN_GB

        # Skip torrents with uploaded = 0
        if uploaded_int == 0:
            continue

        # Single mode: ask for confirmation
        if single_mode:
            print(f"Torrent: {name}")
            print(f"  Current uploaded: {uploaded_gb:.2f} GB")
            confirm = input("  Reset uploaded amount? (y/n): ").strip().lower()
            if confirm != 'y':
                print("  Skipped.\n")
                continue
            print()

        # Reset uploaded amount
        torrent_data[b"total_uploaded"] = (0).to_bytes(uploaded_bytes_len, "big")
        torrents_to_reset.append(name)

        # Re-encode torrent_data back to bencode
        raw[torrent_id] = bencodepy.encode(torrent_data)

    if torrents_to_reset:
        # Create backup
        backup_path = fastresume_path.with_name(
            fastresume_path.name + BACKUP_SUFFIX
        )
        try:
            shutil.copy2(fastresume_path, backup_path)
            print(f"Backup created: {backup_path}")

            # Write changes
            with open(fastresume_path, "wb") as f:
                f.write(bencodepy.encode(raw))

            print(f"\nUploaded amount reset successfully for the following torrents:")
            for i, name in enumerate(torrents_to_reset, 1):
                print(f"{i}. {name}")

            return True

        except Exception as e:
            print(f"Error writing file: {e}")
            return False
    else:
        print("\nNo torrents with uploaded > 0. Nothing to reset.")
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Deluge Upload Resetter - Reset uploaded amount"
    )

    parser.add_argument(
        "-p", "--path",
        type=str,
        help=f"Path to directory containing {DEFAULT_FILENAME} (default: current directory)"
    )

    parser.add_argument(
        "-s", "--single",
        action="store_true",
        help="Prompt for confirmation before resetting each torrent"
    )

    args = parser.parse_args()

    # Determine file path
    if args.path:
        folder = Path(args.path)
        if not folder.is_dir():
            print(f"Error: Directory not found: {folder}")
            sys.exit(1)
        fastresume_path = folder / DEFAULT_FILENAME
    else:
        fastresume_path = Path.cwd() / DEFAULT_FILENAME

    # Run reset
    success = reset_uploads(fastresume_path, single_mode=args.single)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()