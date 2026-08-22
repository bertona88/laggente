#!/bin/sh
set -eu

verify_archive() {
    archive=$1
    listing=$(mktemp) || return 70
    if ! tar -tzf "$archive" >"$listing"; then
        rm -f -- "$listing"
        echo 'upload archive is unreadable or corrupt' >&2
        return 65
    fi
    if awk '
        {
            path = tolower($0)
            if (path ~ /[.](mp3|wav|webm|ogg|oga|opus|m4a|mp4|aac|flac|amr|aiff|aif|caf|mpeg|mpga)$/ ||
                path ~ /(^|\/)([.]?tmp|[.]?temp|[.]?transcription-tmp)(\/|$)/ ||
                path ~ /[.](tmp|temp|part|partial)$/) {
                unsafe = 1
            }
        }
        END { exit unsafe ? 0 : 1 }
    ' "$listing"; then
        rm -f -- "$listing"
        echo 'upload archive contains excluded raw-audio or temporary content' >&2
        return 65
    fi
    rm -f -- "$listing"
    return 0
}

case "${1:-}" in
    create)
        uploads_root=${2:?missing uploads root}
        archive=${3:?missing archive path}
        [ -d "$uploads_root" ] || {
            echo "uploads root is not a directory: $uploads_root" >&2
            exit 66
        }

        exclude_case_option=
        if tar --help 2>&1 | grep -q -- '--exclude-ignore-case'; then
            exclude_case_option=--exclude-ignore-case
        fi

        # Images remain durable. Raw voice-note formats and temporary paths never
        # enter a completed archive, even if application cleanup regresses.
        tar -C "$uploads_root" -czf "$archive" \
            $exclude_case_option \
            --exclude='*.mp3' --exclude='*.MP3' \
            --exclude='*.wav' --exclude='*.WAV' \
            --exclude='*.webm' --exclude='*.WEBM' \
            --exclude='*.ogg' --exclude='*.OGG' \
            --exclude='*.oga' --exclude='*.OGA' \
            --exclude='*.opus' --exclude='*.OPUS' \
            --exclude='*.m4a' --exclude='*.M4A' \
            --exclude='*.mp4' --exclude='*.MP4' \
            --exclude='*.aac' --exclude='*.AAC' \
            --exclude='*.flac' --exclude='*.FLAC' \
            --exclude='*.amr' --exclude='*.AMR' \
            --exclude='*.aiff' --exclude='*.AIFF' \
            --exclude='*.aif' --exclude='*.AIF' \
            --exclude='*.caf' --exclude='*.CAF' \
            --exclude='*.mpeg' --exclude='*.MPEG' \
            --exclude='*.mpga' --exclude='*.MPGA' \
            --exclude='*.tmp' --exclude='*.TMP' \
            --exclude='*.temp' --exclude='*.TEMP' \
            --exclude='*.part' --exclude='*.PART' \
            --exclude='*.partial' --exclude='*.PARTIAL' \
            --exclude='*/tmp' --exclude='*/tmp/*' \
            --exclude='*/TMP' --exclude='*/TMP/*' \
            --exclude='*/.tmp' --exclude='*/.tmp/*' \
            --exclude='*/temp' --exclude='*/temp/*' \
            --exclude='*/TEMP' --exclude='*/TEMP/*' \
            --exclude='*/.temp' --exclude='*/.temp/*' \
            --exclude='*/transcription-tmp' --exclude='*/transcription-tmp/*' \
            --exclude='*/.transcription-tmp' --exclude='*/.transcription-tmp/*' \
            .
        if ! verify_archive "$archive"; then
            rm -f -- "$archive"
            exit 65
        fi
        ;;
    verify)
        archive=${2:?missing archive path}
        [ -f "$archive" ] || {
            echo "upload archive not found: $archive" >&2
            exit 66
        }
        verify_archive "$archive"
        ;;
    *)
        echo 'usage: archive-uploads.sh {create UPLOADS_ROOT ARCHIVE|verify ARCHIVE}' >&2
        exit 64
        ;;
esac
