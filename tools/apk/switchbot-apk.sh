#!/usr/bin/env bash
set -e

# SwitchBot APK Download, Extract & Decompile
# Stages: download -> unpack -> decompile
#
# Output goes to <repo-root>/decomp/ (override with -w or $WORK_DIR):
#   download/  raw .xapk / .apk
#   apks/      split APKs unzipped from the XAPK
#   dex/       extracted .dex
#   lib/       native .so
#   src/       decompiled + pruned Java   <- the thing you read
#   VERSION    app version that produced the above

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
WORK_DIR="${WORK_DIR:-$ROOT/decomp}"
PACKAGE="com.theswitchbot.switchbot"

usage() {
    cat <<EOF
Usage: $0 <command> [options]

Commands:
    download    Download APK using apkeep
    unpack      Unpack XAPK and extract DEX + native libs
    decompile   Decompile DEX with jadx
    all         Run all stages

Options:
    -w DIR      Working directory (default: \$repo_root/decomp)
    -v VER      Specific version to download
    -l          List available versions

Environment:
    WORK_DIR    Working directory
EOF
    exit 1
}

# Check for required tools
check_deps() {
    local missing=()
    for cmd in "$@"; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "Missing required tools: ${missing[*]}"
        exit 1
    fi
}

# Download using apkeep
download_apk() {
    local version="$1"
    local list_only="$2"

    check_deps apkeep

    mkdir -p "$WORK_DIR/download"

    echo "=== Stage: Download ==="

    if [[ "$list_only" == "true" ]]; then
        echo "Available versions:"
        apkeep -a "$PACKAGE" -l "$WORK_DIR/download"
        return 0
    fi

    local app_spec="$PACKAGE"
    if [[ -n "$version" ]]; then
        app_spec="${PACKAGE}@${version}"
    fi

    echo "Downloading $app_spec from APKPure..."
    apkeep -a "$app_spec" -d apk-pure "$WORK_DIR/download"

    # Find what was downloaded
    local downloaded="$(ls -t "$WORK_DIR/download/"*.xapk "$WORK_DIR/download/"*.apk 2>/dev/null | head -1)"

    if [[ -n "$downloaded" ]]; then
        echo ""
        echo "Downloaded: $downloaded"
        echo "Size: $(du -h "$downloaded" | cut -f1)"

        # Create symlink to latest
        local ext="${downloaded##*.}"
        ln -sf "$(basename "$downloaded")" "$WORK_DIR/download/latest.$ext"
    else
        echo "No APK/XAPK found after download"
        return 1
    fi
}

# Unpack XAPK and extract DEX + native libs
unpack_xapk() {
    check_deps unzip jq

    echo "=== Stage: Unpack ==="

    # Find XAPK to unpack (resolve symlinks)
    local xapk="$(ls -t "$WORK_DIR/download/"*.xapk 2>/dev/null | head -1)"

    if [[ -z "$xapk" ]]; then
        echo "No XAPK found in $WORK_DIR/download/"
        echo "Run 'download' stage first"
        return 1
    fi

    xapk="$(readlink -f "$xapk")"

    # Record the version that produced this working dir
    local version="$(unzip -p "$xapk" manifest.json | jq -r '.version_name')"
    echo "$version" > "$WORK_DIR/VERSION"

    # Step 1: Unzip XAPK to get APK files
    if [[ -d "$WORK_DIR/apks" ]]; then
        echo "Already unpacked: $WORK_DIR/apks"
    else
        echo "Unpacking XAPK: $xapk (version $version)"
        mkdir -p "$WORK_DIR/apks"
        unzip -q "$xapk" -d "$WORK_DIR/apks"
    fi

    # Step 2: Extract DEX from base APK
    local base_apk="$(find "$WORK_DIR/apks" -maxdepth 1 -name "*.apk" ! -name "config.*" ! -name "*_assets.apk" | head -1)"

    if [[ -n "$base_apk" && ! -d "$WORK_DIR/dex" ]]; then
        echo "Extracting DEX from: $(basename "$base_apk")"
        mkdir -p "$WORK_DIR/dex"
        unzip -q -o "$base_apk" "*.dex" -d "$WORK_DIR/dex/"
        echo "  DEX files: $(ls "$WORK_DIR/dex/"*.dex 2>/dev/null | wc -l)"
    fi

    # Step 3: Extract native libs from arm64 APK
    local arm64_apk="$(find "$WORK_DIR/apks" -maxdepth 1 -name "config.arm64*.apk" | head -1)"

    if [[ -n "$arm64_apk" && ! -d "$WORK_DIR/lib" ]]; then
        echo "Extracting native libs from: $(basename "$arm64_apk")"
        mkdir -p "$WORK_DIR/lib"
        unzip -q -o "$arm64_apk" "lib/arm64-v8a/*.so" -d "$WORK_DIR/lib/" 2>/dev/null || true
        echo "  Native libs:"
        ls "$WORK_DIR/lib/lib/arm64-v8a/"*.so 2>/dev/null | xargs -I{} basename {} | sed 's/^/    /'
    fi

    echo ""
    echo "Output: $WORK_DIR (version $version)"
    echo "  apks/  - APK files from XAPK"
    echo "  dex/   - DEX files for decompilation"
    echo "  lib/   - Native libraries"
}

# Decompile DEX to Java source
decompile_dex() {
    check_deps jadx

    echo "=== Stage: Decompile ==="

    if [[ ! -d "$WORK_DIR/dex" ]]; then
        echo "No DEX files found in $WORK_DIR/dex"
        echo "Run 'unpack' stage first"
        return 1
    fi

    local out_dir="$WORK_DIR/src"

    if [[ -d "$out_dir" ]]; then
        echo "Already decompiled: $out_dir"
        return 0
    fi

    echo "Decompiling DEX files..."
    jadx --show-bad-code --no-res --no-debug-info \
        --use-kotlin-methods-for-var-names apply-and-hide \
        -d "$out_dir" \
        "$WORK_DIR/dex/"*.dex 2>&1 | tail -5

    # Prune to protocol-relevant packages
    echo ""
    echo "Pruning to relevant packages..."

    local keep_dirs=(
        "com/theswitchbot/device/protocol"
        "com/theswitchbot/device/impl"
        "com/theswitchbot/device/consts"
        "com/theswitchbot/device/abs"
        "com/theswitchbot/device/control"
        "com/theswitchbot/connector"
        "com/thingclips/ble"
    )

    local src_base="$out_dir/sources"
    if [[ -d "$src_base" ]]; then
        mkdir -p "$WORK_DIR/src-pruned"

        for dir in "${keep_dirs[@]}"; do
            if [[ -d "$src_base/$dir" ]]; then
                mkdir -p "$WORK_DIR/src-pruned/$(dirname "$dir")"
                cp -r "$src_base/$dir" "$WORK_DIR/src-pruned/$dir"
            fi
        done

        rm -rf "$out_dir"
        mv "$WORK_DIR/src-pruned" "$out_dir"
    fi

    echo ""
    echo "Output: $out_dir"
    find "$out_dir" -type d -maxdepth 4 | head -20
}

# Parse command first, then options
CMD="${1:-usage}"
shift || true

LIST_VERSIONS=false
while getopts "w:v:lh" opt; do
    case "$opt" in
        w) WORK_DIR="$OPTARG" ;;
        v) VERSION="$OPTARG" ;;
        l) LIST_VERSIONS=true ;;
        h) usage ;;
        *) usage ;;
    esac
done
shift $((OPTIND-1))

case "$CMD" in
    download)
        download_apk "$VERSION" "$LIST_VERSIONS"
        ;;
    unpack)
        unpack_xapk
        ;;
    decompile)
        decompile_dex
        ;;
    all)
        download_apk "$VERSION" "$LIST_VERSIONS"
        unpack_xapk
        decompile_dex
        ;;
    *)
        usage
        ;;
esac
