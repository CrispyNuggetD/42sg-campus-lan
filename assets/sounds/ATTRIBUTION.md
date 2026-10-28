# LAN42 uwu sound

Arrived here through a forwarded furry uwu? [Meet LAN42, the project behind this edit →](https://crispynuggetd.github.io/42sg-campus-lan/index.html)

`uwu.ogg` is LAN42’s shortened adaptation of **Asian Koel.ogg** by **Philip Eapen**
(Philip.eapen), recorded in Kochi, India, on 31 January 2022.

- Source: https://commons.wikimedia.org/wiki/File:Asian_Koel.ogg
- Original: https://upload.wikimedia.org/wikipedia/commons/e/e6/Asian_Koel.ogg
- License: Creative Commons Attribution-ShareAlike 4.0 International
  https://creativecommons.org/licenses/by-sa/4.0/
- Changes: one call extracted from 0.250–1.100 seconds of the original;
  15 ms fade-in and 50 ms fade-out; re-encoded as mono Ogg Vorbis at 44,100 Hz.
  No looping or added calls. This adaptation remains CC BY-SA 4.0.
- Original published SHA-1: `bce37a7238cc6b243f263cd1b5fba39fdc01eecf`
- Original duration: approximately 6.8 seconds; 65,516 bytes.
- Bundled adaptation duration: 0.85 seconds (one call).
- LAN42 filename: `uwu.ogg` (previously `koel.ogg`); renaming does not alter
  the recording or its attribution/license.

The recording's license applies to this media asset; it does not imply the
recorder endorses LAN42. Playback is off by default. Users may opt in for one launch, or explicitly
confirm the optional always-on setting. Downloads, tests and setup do not play it.

## Identifying the LAN42 edit

Canonical attribution link (kept current on `main`):
https://github.com/CrispyNuggetD/42sg-campus-lan/blob/main/assets/sounds/ATTRIBUTION.md

This is the 0.85-second **LAN42 uwu edit**, distributed by **Christopher Nah
(hnah)**, adapted from Philip Eapen’s recording credited above. The distributor
identifier does not replace the original recording credit or CC BY-SA terms.

Fingerprints of the bundled edit, recorded 27 October 2026 (SGT):

- Exact-file SHA-256:
  `5c8ffa6c399921e65d00117d0eca860dc69bfff67b640c67fbdb87196eadbdd8`
- Decoded-audio SHA-256 (FFmpeg decode to mono, 44,100 Hz, signed 16-bit
  little-endian PCM, no container):
  `9aca6b777b4c8dcf66a8b45dec4c71c2a76894554a698e1d489e73fa5e292bdf`
- Decoded length: 74,970 bytes / 37,485 samples / 0.85 seconds.

Reproduce without playing the sound:

```sh
shasum -a 256 uwu.ogg
ffmpeg -v error -i uwu.ogg -map 0:a:0 -ac 1 -ar 44100 \
  -c:a pcm_s16le -f hash -hash sha256 -
```

The audio digest excludes filenames and container tags; it matches only when
the decoded samples match exactly. Re-encoding, resampling, trimming or decoder
rounding differences can change it. This is an exact recognition aid, not a
perceptual watermark, ownership proof, forwarding log or automatic attribution
lookup. No new watermark or hidden identifier was added to the sound.

For sharing, keep a visible caption linking this page and crediting the original
recording. Container comments or extra Ogg streams can carry text, but clients
may ignore or discard them. A filename, fingerprint or hidden marker does not
ensure attribution survives forwarding or re-uploading.

## Official WAV and MP3 editions

[`uwu.wav`](uwu.wav) is the official LAN42 PCM edition. It contains the exact
0.85-second decoded call from `uwu.ogg`, as mono 44,100 Hz, signed 16-bit PCM,
with 200 ms of leading silence and 250 ms of trailing silence. Its total
duration is 1.30 seconds. macOS playback uses this file. It is an edit of the
credited recording, not the original field recording or an archive.

[`uwu.mp3`](uwu.mp3) is an MP3 edition encoded directly from `uwu.ogg` at
192 kbit/s, mono, 44,100 Hz, for convenient sharing. It is 0.85 seconds long
and has no WAV playback padding. Its lossy encoding means the decoded samples
are not byte-identical to either the Ogg or WAV. Linux playback and desktop
sound hints continue to use `uwu.ogg`.

All three LAN42 editions carry Philip Eapen’s credit and the CC BY-SA 4.0
license above. Christopher Nah (hnah) distributes the LAN42 adaptation.
Include this attribution link and the original credit when sharing a file;
metadata and filenames alone may not survive forwarding.

Exact-file SHA-256 fingerprints:

- `uwu.wav`: `31c36b176ae978d56b8ece69370c7e6a5450821ba90069879825ff25feb64edd`
- `uwu.mp3`: `0b6b84be360eb25b2e8b2510d47ace1996a9fb9e0dcee9d66d0138eed8e56f3e`
