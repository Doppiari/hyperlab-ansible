#!/usr/bin/env bash
# build-shaders.sh - compile the shell's shaders and keep their manifest.
#
#   tools/build-shaders.sh [DIR]          rebuild every .qsb and SHADERS.sha256
#   tools/build-shaders.sh --check [DIR]  verify the committed files
#
# DIR defaults to the shell's shaders/ directory. Every *.frag and *.vert
# there is compiled with Qt Shader Tools (qsb, Arch package qt6-shadertools)
# into a .qsb next to it. SHADERS.sha256 records `qsb --version` on its first
# line, then the SHA-256 of every source and of every .qsb.
#
# --check refuses a missing, unreadable, duplicated, unlisted or redirected
# input and any digest that differs. Wherever a qsb is found, whatever its
# version, it also rebuilds every shader into a temporary directory and
# requires the committed bytes; when that qsb is not the recorded one and the
# bytes differ, the shaders must be rebuilt with it and committed. Without
# any qsb it says the rebuild was skipped and why; the digests are still
# checked.
#
# The host never runs this: the role installs the committed .qsb files, so
# the host needs no shader compiler. HYPERLAB_QSB names the qsb to use;
# otherwise it is looked up in PATH, then in HYPERLAB_QT_BINDIR, the
# directory where the distribution installs Qt's tools (/usr/lib/qt6/bin on
# Arch, the default).
set -uo pipefail

readonly MANIFEST_NAME=SHADERS.sha256
readonly -a QSB_TARGETS=(--glsl "100 es,120,150" --hlsl 50 --msl 12)

fail() {
    printf 'build-shaders: %s\n' "$*" >&2
    return 1
}

# Print the qsb to use, or nothing when none is installed. A named qsb that
# does not run is an error, never a skip.
find_qsb() {
    local candidate=""

    if [[ -n "${HYPERLAB_QSB:-}" ]]; then
        [[ -x "${HYPERLAB_QSB}" ]] || { fail "HYPERLAB_QSB is not executable: ${HYPERLAB_QSB}"; return 1; }
        printf '%s\n' "${HYPERLAB_QSB}"
        return 0
    fi
    local bindir="${HYPERLAB_QT_BINDIR:-/usr/lib/qt6/bin}"

    candidate="$(command -v qsb 2>/dev/null)" || candidate=""
    if [[ -z "${candidate}" && -x "${bindir}/qsb" ]]; then
        candidate="${bindir}/qsb"
    fi
    [[ -n "${candidate}" ]] && printf '%s\n' "${candidate}"
    return 0
}

qsb_version() {
    local qsb="$1"
    local version=""

    version="$("${qsb}" --version 2>/dev/null)" || { fail "${qsb} --version failed"; return 1; }
    [[ "${version}" =~ ^qsb\ [0-9]+\.[0-9]+(\.[0-9]+)?$ ]] \
        || { fail "unexpected qsb version: ${version}"; return 1; }
    printf '%s\n' "${version}"
}

# Every shader source in DIR, sorted. A redirected source is a refusal.
list_sources() {
    local dir="$1"
    local path=""
    local -a names=()

    for path in "${dir}"/*.frag "${dir}"/*.vert; do
        [[ -e "${path}" || -L "${path}" ]] || continue
        [[ -f "${path}" && ! -L "${path}" ]] || { fail "not a regular file: ${path}"; return 1; }
        names+=("${path##*/}")
    done
    (( ${#names[@]} > 0 )) || { fail "no shader source in ${dir}"; return 1; }
    printf '%s\n' "${names[@]}" | LC_ALL=C sort
}

digest() {
    local path="$1"
    local line=""

    [[ -f "${path}" && ! -L "${path}" ]] || { fail "not a regular file: ${path}"; return 1; }
    line="$(sha256sum -- "${path}")" || { fail "cannot read ${path}"; return 1; }
    printf '%s\n' "${line%% *}"
}

compile() {
    local qsb="$1"
    local source="$2"
    local output="$3"

    "${qsb}" "${QSB_TARGETS[@]}" -o "${output}" "${source}" >/dev/null \
        || { fail "qsb failed on ${source}"; return 1; }
    [[ -s "${output}" ]] || { fail "qsb wrote nothing for ${source}"; return 1; }
}

build() {
    local dir="$1"
    local qsb=""
    local version=""
    local name=""
    local file=""
    local sum=""
    local manifest=""
    local -a sources=()

    qsb="$(find_qsb)" || return 1
    [[ -n "${qsb}" ]] || { fail "qsb not found: install qt6-shadertools"; return 1; }
    version="$(qsb_version "${qsb}")" || return 1
    mapfile -t sources < <(list_sources "${dir}") || return 1
    (( ${#sources[@]} > 0 )) || return 1

    manifest="$(mktemp "${dir}/.${MANIFEST_NAME}.XXXXXX")" || { fail "cannot write in ${dir}"; return 1; }
    printf '%s\n' "${version}" >"${manifest}" || { rm -f -- "${manifest}"; return 1; }
    for name in "${sources[@]}"; do
        compile "${qsb}" "${dir}/${name}" "${dir}/${name}.qsb" || { rm -f -- "${manifest}"; return 1; }
        for file in "${name}" "${name}.qsb"; do
            sum="$(digest "${dir}/${file}")" || { rm -f -- "${manifest}"; return 1; }
            printf '%s  %s\n' "${sum}" "${file}" >>"${manifest}" || { rm -f -- "${manifest}"; return 1; }
        done
        printf 'built %s.qsb\n' "${name}"
    done
    chmod 0644 -- "${manifest}" || { rm -f -- "${manifest}"; return 1; }
    mv -f -- "${manifest}" "${dir}/${MANIFEST_NAME}" || { rm -f -- "${manifest}"; return 1; }
    printf 'recorded %s with %s\n' "${MANIFEST_NAME}" "${version}"
}

check() {
    local dir="$1"
    local manifest="${dir}/${MANIFEST_NAME}"
    local recorded=""
    local line=""
    local name=""
    local expected=""
    local actual=""
    local path=""
    local qsb=""
    local version=""
    local origin=""
    local scratch=""
    local -a lines=()
    local -a sources=()
    local -A listed=()
    local -A wanted=()

    [[ -f "${manifest}" && ! -L "${manifest}" && -r "${manifest}" ]] \
        || { fail "missing or redirected manifest: ${manifest}"; return 1; }
    mapfile -t lines <"${manifest}" || { fail "cannot read ${manifest}"; return 1; }
    (( ${#lines[@]} > 1 )) || { fail "empty manifest: ${manifest}"; return 1; }
    recorded="${lines[0]}"
    [[ "${recorded}" =~ ^qsb\ [0-9]+\.[0-9]+(\.[0-9]+)?$ ]] \
        || { fail "the manifest does not start with the qsb version"; return 1; }

    for line in "${lines[@]:1}"; do
        [[ "${line}" =~ ^([0-9a-f]{64})\ \ ([A-Za-z0-9._-]+)$ ]] \
            || { fail "malformed manifest line: ${line}"; return 1; }
        name="${BASH_REMATCH[2]}"
        [[ -z "${listed[${name}]:-}" ]] || { fail "listed twice: ${name}"; return 1; }
        listed["${name}"]="${BASH_REMATCH[1]}"
    done

    mapfile -t sources < <(list_sources "${dir}") || return 1
    (( ${#sources[@]} > 0 )) || return 1
    for name in "${sources[@]}"; do
        wanted["${name}"]=1
        wanted["${name}.qsb"]=1
    done
    wanted["${MANIFEST_NAME}"]=1
    for path in "${dir}"/* "${dir}"/.[!.]*; do
        [[ -e "${path}" || -L "${path}" ]] || continue
        [[ -n "${wanted[${path##*/}]:-}" ]] || { fail "unexpected file: ${path}"; return 1; }
    done
    for name in "${!wanted[@]}"; do
        [[ "${name}" == "${MANIFEST_NAME}" ]] && continue
        expected="${listed[${name}]:-}"
        [[ -n "${expected}" ]] || { fail "not in the manifest: ${name}"; return 1; }
        actual="$(digest "${dir}/${name}")" || return 1
        [[ "${actual}" == "${expected}" ]] \
            || { fail "${name} does not match the manifest: run tools/build-shaders.sh"; return 1; }
    done
    for name in "${!listed[@]}"; do
        [[ -n "${wanted[${name}]:-}" && "${name}" != "${MANIFEST_NAME}" ]] \
            || { fail "the manifest lists ${name}, which is not a shader or its .qsb"; return 1; }
    done

    qsb="$(find_qsb)" || return 1
    if [[ -z "${qsb}" ]]; then
        printf 'rebuild skipped: qsb not found (qt6-shadertools); the digests match the manifest\n'
        return 0
    fi
    version="$(qsb_version "${qsb}")" || return 1
    origin=""
    if [[ "${version}" != "${recorded}" ]]; then
        origin=" (recorded with ${recorded})"
    fi
    scratch="$(mktemp -d)" || { fail "cannot create a temporary directory"; return 1; }
    for name in "${sources[@]}"; do
        if ! compile "${qsb}" "${dir}/${name}" "${scratch}/${name}.qsb"; then
            rm -rf -- "${scratch}"
            return 1
        fi
        if ! cmp -s -- "${scratch}/${name}.qsb" "${dir}/${name}.qsb"; then
            rm -rf -- "${scratch}"
            if [[ -n "${origin}" ]]; then
                fail "${name}.qsb is not what ${version} builds from ${name}${origin}:" \
                    "run tools/build-shaders.sh with ${version} and commit the result"
            else
                fail "${name}.qsb is not what ${version} builds from ${name}: run tools/build-shaders.sh"
            fi
            return 1
        fi
    done
    rm -rf -- "${scratch}"
    printf 'rebuild: %d shader(s) byte-identical with %s%s\n' "${#sources[@]}" "${version}" "${origin}"
}

main() {
    local root=""
    local mode=build
    local dir=""

    root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)" || return 1
    if [[ "${1:-}" == "--check" ]]; then
        mode=check
        shift
    fi
    (( $# <= 1 )) || { fail "usage: tools/build-shaders.sh [--check] [DIR]"; return 1; }
    dir="${1:-${root}/roles/host_desktop_common/files/quickshell/hyperlab/shaders}"
    [[ -d "${dir}" && ! -L "${dir}" ]] || { fail "not a shader directory: ${dir}"; return 1; }
    "${mode}" "${dir}"
}

main "$@"
