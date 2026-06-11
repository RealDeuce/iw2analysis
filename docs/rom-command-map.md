# ImageWriter II ROM Command Map

This file ties the programmer-visible command set to the `ImageWriter2_new.bin`
ROM. It is a working map for emulator implementation, not a fully symbolic
disassembly.

Primary listing:

```sh
../mame/unidasm ImageWriter2_new.bin -arch upd7810 -basepc 0 -count 0x8000 > disasm/iw2_upd7810_full.lst
```

## Parser Model

Serial input is interrupt-driven but command execution is deferred:

- `0x2102` is the serial interrupt entry. It reads `RXB` and calls `0x2137`.
- `0x2137` appends the byte to the receive/print buffer and updates `AA00` and
  `AA04`.
- `0x3BFC` is the buffered byte consumer used by the print/parser path.
- `CALT ($00A4)` vectors to `0x3BFC`, so many command handlers fetch their
  numeric/string parameters through the same buffered path.
- `CALT ($00B6)` vectors to `0x3D07`, which calls `0x3BFC` and then applies the
  eighth-bit policy controlled by `AA6B` bit `0x20`.

This confirms the manuals' behavioral warning: commands received over serial are
buffered with printable data and are not necessarily acted on at interrupt time.

## Control Character Dispatch

Single-byte controls are documented at the command-reference level in
`docs/imagewriter-ii-command-reference.md`. The ROM dispatches them through the
main command loop at `0x2748`, not through the ESC command table. The loop fetches
one byte with `CALT ($00B6)`, special-cases `CTRL-H` (`0x08`) through `0x368C`,
then uses the keyed dispatch table at `0x28B0`.

`0x28B0-0x28D6` is data, although the raw disassembler listing decodes it as
code. Helper `0x2CCF` saves the fetched byte in `C`, scans three-byte entries of
`key, target-low, target-high`, and returns the selected target in `EA`; the main
loop copies that target to `BC` and calls it with `CALB`.

Decoded control dispatch table:

| Key | Command | Handler | Status |
| ---: | --- | ---: | --- |
| `0x1B` | `ESC` | `0x2C07` | high |
| `0x09` | `CTRL-I` / horizontal tab | `0x3718` | high |
| `0x0A` | `CTRL-J` / line feed | `0x3799` | high |
| `0x0B` | `CTRL-K` / fixed micro-feed command | `0x37A4` | high |
| `0x0C` | `CTRL-L` / form feed | `0x37B1` | high |
| `0x0D` | `CTRL-M` / carriage return | `0x36F5` | high |
| `0x0E` | `CTRL-N` / double-width on | `0x370D` | high |
| `0x0F` | `CTRL-O` / double-width off | `0x3706` | high |
| `0x13` | `CTRL-S` / deselect or flow-control-related command | `0x37CB` | high |
| `0x18` | `CTRL-X` / erase current staged line | `0x37C8` | high |
| `0x1D` | `CTRL-]` / undocumented vertical-format/setup parser | `0x37D7` | medium-low |
| `0x1F` | `CTRL-_ n` / feed blank lines | `0x3748` | high |
| `0xFF` | default for unmatched bytes | `0x28D7` | high |

The default path at `0x28D7` stores the current byte in `AA12`, sends printable
bytes to the character renderer, and routes non-table controls through the
renderer/control fallback around `0x2B5D` and `0x2B81`.

The eighth-bit switch is important here. `0x3D07` masks incoming bytes with
`0x7F` when `AA6B bit 0x20` says to ignore the eighth bit, so `0x80-0x9F` become
ordinary `0x00-0x1F` controls. When the eighth bit is included, the high-bit
control-code twins can bypass the low-control dispatch table and continue into
the high-ASCII/custom-character rendering logic around `0x28F0`, `0x2B70`, and
`0x2B81`.

The control path still needs more symbolic naming, but these anchors are useful
for emulator work:

| Control | Meaning | ROM anchor | Confidence | Notes |
| --- | --- | ---: | --- | --- |
| `CTRL-G` (`0x07`) | Bell | `0x017C-0x0184`, `0x43CF` | medium | Early path compares against `0x07` and conditionally jumps to the bell/control routine. |
| `CTRL-H` (`0x08`) | Backspace / overprint path | `0x274A -> 0x368C` | high | Special-cased before the table. In the normal overprint path it fetches the next printable byte, saves it in `AA08`, backs `AA3C` up by that byte's rendered advance, calls the shared line-position reset path, then sends the saved byte through `0x28D7`. |
| `CTRL-I` (`0x09`) | Horizontal tab | `0x3718` | high | Walks the `A9C0+` tab table and advances `AA26` to the next tab stop. |
| `CTRL-J` (`0x0A`) | Line feed / print trigger | `0x3799` | high | Calls `0x3DB1` print-trigger check, then `0x3DDD` line feed when allowed. |
| `CTRL-K` (`0x0B`) | Undocumented fixed micro-feed | `0x37A4` | high | Same print-trigger gate as LF, then feeds by a fixed `0x0002` unit through `0x3DF5` and falls into the common line-reset path at `0x37BE`. |
| `CTRL-L` (`0x0C`) | Form feed / print trigger | `0x37B1` | high | Uses current line spacing/form state through `AA6D`, `0x3DFE`, and the common print/reset path. |
| `CTRL-M` (`0x0D`) | Carriage return / print trigger | `0x36F5` | high | Calls `0x3B19`, optionally auto-feeds when `AA6A bit 0x80` is active, then jumps to the line reset path. |
| `CTRL-N` (`0x0E`) | Double-width on | `0x370D` | high | Sets `AA5B bit 0x04`. |
| `CTRL-O` (`0x0F`) | Double-width off | `0x3706` | high | Clears `AA5B bit 0x04`. |
| `CTRL-Q` (`0x11`) | Select / DCI byte | `0x3C47-0x3C52`, `0x03F9` | high | The byte consumer recognizes `0x11` specially so it can reselect the printer; the select routine sets the hardware-selected/DTR state. It is honored only when software select response is enabled. |
| `CTRL-S` (`0x13`) | Deselect / DC3 byte | `0x37CB -> 0x0449` | high | Checks `AA6A bit 0x10`; when the bit is clear, software select response is enabled and execution reaches the deselect path at `0x0449`. When set, it returns without action. |
| `CTRL-X` (`0x18`) | Erase/reset current line path | `0x37C8 -> 0x275D` | high | Jumps directly to the shared line finalize/reset path without the CR/LF/FF print-trigger gate. It cancels the current staged line when the parser reaches `CTRL-X`; already printed lines are unaffected. |
| `CTRL-]` (`0x1D`) | Undocumented vertical-format/setup table parser | `0x37D7` | medium | Waits for pending buffered state to drain, clears an `A948+` state block, copies `AA6D` to `A950`, then parses `A@`, a bounded list of `x@` records, terminal `A@`, and one consumed lookahead byte. See the dedicated section below. |
| `CTRL-_ n` (`0x1F n`) | Feed `n` blank lines | `0x3748` | high | Fetches a parameter through `CALT ($00A4)`, masks it to `0x1F`, and loops through the line-feed path. |

For emulation, do not implement `0x80-0x9F` as unconditional aliases for
`0x00-0x1F`; that aliasing is conditional on the eighth-bit ignore/include
setting.

Treat the low-confidence rows as entry points for tracing, not as final behavior
specifications. The ESC table below is much more directly decoded.

## Undocumented CTRL-] Structured Command

`CTRL-]` (`0x1D`) is not a printable fallback in the normal low-control path. It
is a real control-table entry at `0x37D7` and parses a framed, undocumented
vertical-format/setup table. The manuals extracted so far do not describe this
syntax.

Observed handler shape:

| Address | Behavior |
| --- | --- |
| `0x37D7` | Calls `0x3CDA`, then waits until pending state pointer/count `AA54` is zero. |
| `0x37E4-0x37E9` | Clears `0x6E` bytes starting at `A948` with helper `0x3A22`. |
| `0x37EC-0x3801` | Copies current line spacing `AA6D` to `A950`; initializes `A94A`, `A94C`, and `A8E0` to either `0x0000` or `AA6D`, depending on `BIT 3,VV:2D`. |
| `0x3805-0x3816` | Fetches two bytes and requires an `A@` prefix. The first byte is masked with `0x7F`; the delimiter byte must be literal `@` (`0x40`). |
| `0x3817-0x386C` | Stores the initial `A` at `A955`, sets row counter `AA6F = 1`, then parses `x@` records. Body record bytes are masked with `0x7F`; delimiter bytes must be literal `@`. |
| `0x386E-0x3897` | Terminal `A@` stores an `A` marker at the current table slot, computes `A948 = low(A950) * AA6F`, requires that value to be greater than `0x0090`, then computes `A94C = A952 = low(A950) * A954`. |
| `0x3897-0x389A` | Fetches one lookahead/trailer byte through `CALT ($00B6)`. If it is not `0x1E`, the command returns normally. |
| `0x389B-0x389F` | If the lookahead byte is `0x1E` (`CTRL-^`), the skipped `RET` drops into a non-returning loop: optional first `EXH`, then repeated `EXH; INX DE; JR 0x389D`. Interrupts can still run, but this command handler does not return. |
| `0x38A0-0x38BB` | No cross-reference or fall-through from the `CTRL-]` path reaches this adjacent byte range. It references `A948`, `A8DA`, and `AA6B`, but should be treated as dead code or data until a real entry is found. |

Accepted grammar from the parser:

```text
CTRL-]  A @  body  A @  trailer

body := zero or more x @ records
x    := any 7-bit even byte, after x &= 0x7F
trailer := one consumed byte; 0x1E enters the non-returning loop
```

More precisely:

- The required prefix is `A@`. The initial `A` is stored at `A955` and counted
  as row 1.
- Each even `x` record is stored at the next `A955+` slot and increments row
  count `AA6F`. To reach a normal terminator, `AA6F` must remain below `0x62`,
  so the practical maximum is 97 counted rows including the initial `A`.
- In one state mode, each even `x` record also increments `A954`; this is gated
  by `BIT 5,VV:2D`.
- Terminal `A@` is accepted only after the prefix/body. It is stored as an end
  marker but does not increment `AA6F`.
- Odd `x` records other than `A` and `C` abort the command after consuming the
  record delimiter.
- `C@` is a special early-return form at `0x383B-0x3840`; its user-visible
  purpose is not yet clear and it does not take the terminal `CTRL-^` path.
- A terminal `A@` frame is rejected unless `low(A950) * AA6F > 0x0090`. Since
  `A950` is copied from current line spacing `AA6D`, this is effectively a
  minimum form length check greater than one inch.
- After the terminal `A@`, the handler always consumes one more byte with the
  normal eighth-bit policy. If that byte is not `0x1E`, the command returns.
  If it is `0x1E`, the firmware enters the non-returning loop at `0x389D`.

The best current interpretation is "download a vertical form table": one stored
byte per vertical row, with line spacing determining the physical form length.
For command-level emulation, do not render `CTRL-]` frames. A practical emulator
can consume the frame as an opaque setup command and should treat a post-table
`0x1E` as a firmware-hang case, not as successful command completion.

## Current-Line Erase

`CTRL-X` is the erase-current-line command. In the ROM it is a direct jump from
table target `0x37C8` into shared reset/finalize routine `0x275D`; it does not
call the CR/LF/FF print-trigger check at `0x3DB1` and does not call the line-feed
motion path at `0x3DDD`.

User-visible behavior for emulation:

- The command takes effect when the parser consumes `0x18` from the buffered
  input stream.
- It cancels the not-yet-printed contents of the current line.
- It does not cause paper motion and does not print the erased contents.
- Bytes already printed by an earlier print trigger are not affected.
- Following printable bytes are staged on the same physical line from the reset
  horizontal position.

Important implementation side effects in `0x275D`:

| Address | Behavior |
| --- | --- |
| `0x278B-0x2796` | Clears `AA5C` and restores active line-buffer pointer `AA3A` from saved base `AA52`. |
| `0x279B-0x279F` | Restores current horizontal position `AA26` from `AA3C`. |
| `0x27A3-0x27B0` | Emits several zero/state records through `CALT ($00AA)` / `CALT ($00AC)` and `0x3BBC`, keeping the internal staged-record counters consistent. |
| `0x27B3-0x27BA` | Clears `AA44`, the accumulated dot/graphics-width state. |

So a stream like `ABC CTRL-X DEF CR` should print only `DEF` on that line. A
stream like `ABC CR CTRL-X DEF CR` has already committed `ABC` before `CTRL-X`
is processed, so only the second line is affected.

## Paper Feed And Form State

The command parser does not step the paper-feed motor directly. Paper-motion
commands enqueue vertical-motion records in the print/output record stream via
`0x3B8C`, then the scheduler and motor routines consume those records later.
For a command-level emulator, model the parsed feed records and form counters;
cycle-accurate stepper timing can stay below this layer.

Feed record builders:

| Source command | Handler path | Record type bits | Amount |
| --- | --- | --- | --- |
| `LF` / `CTRL-J` | `0x3799 -> 0x3DDD` | `0x80 | AA6C` | Current line spacing `AA6D`. |
| `CR` auto-LF | `0x36F5 -> 0x3DDD` when `AA6A bit 0x80` is set | `0x80 | AA6C` | Current line spacing `AA6D`. |
| `CTRL-_ n` | `0x3748`, repeated calls to `0x3DDD` | `0x80 | AA6C` | `n` lines of current line spacing. |
| `CTRL-K` | `0x37A4 -> 0x3DF5 -> 0x37BE` | `0xC0 | AA6C` | Fixed `0x0002` unit, then common line reset. |
| `FF` / `CTRL-L` | `0x37B1 -> 0x3DFE` | `0xA0 | AA6C` | Current line spacing `AA6D`, with form-feed record type. |
| Full-line auto-feed | `0x2782 -> 0x3E07` | `0xE0 | AA6C` | Current line spacing `AA6D`. |

`AA6C` is the feed direction byte. `ESC f` stores `0x00` for forward feed and
`ESC r` stores `0x04` for reverse feed. The helpers OR this byte into the high
byte of each feed record, so direction is carried with the queued motion rather
than applied as a global side effect later.

Page/form state:

| State | Meaning | Evidence |
| --- | --- | --- |
| `A8DA` | Page length in 1/144 inch units. | Reset initializes it from SW1-4 to `0x0630` (11 inches) or `0x06C0` (12 inches). `ESC H nnnn` stores the parsed value here. |
| `A8E0` | Current form position used by the feed scheduler. | Reset and `ESC H` initialize it; feed scheduler paths compare/update it; `ESC v` writes only this word. |
| `A8DC/A8DE` | Perforation-skip offsets/counters. | Reset and `ESC H` initialize them to `0x0048` when perforation skip is enabled or `0x0000` when disabled. `ESC D/Z ... 04` update them on software-switch transitions; disabling skip restores `A8DE` from `A8E4`. |
| `A8E2` | Saved/default line spacing for form logic. | Reset stores `0x0018`, matching default `AA6D`. |
| `A8E4` | Saved perforation-skip/form baseline. | Reset copies the same initialized perforation-skip value used for `A8DC/A8DE/A8E0`; `ESC D` restoring skip-disabled state copies it back to `A8DE`. |

Perforation skip polarity is now tied to the ROM and the manual:

- `AA6B bit 0x04` set means perforation skip is disabled.
- `AA6B bit 0x04` clear means perforation skip is enabled.
- `ESC D 00 04` sets the bit. When the command newly disables perforation skip,
  it zeroes `A8DC` and `A8E0`, and copies saved baseline `A8E4` back to
  `A8DE`.
- `ESC Z 00 04` clears the bit. When the command newly enables perforation skip,
  it initializes `A8DC` and `A8E0` to `0x0048` and clamps `A8DE` to at least
  `0x0048`.

`ESC H nnnn` is page length. With perforation skip enabled, the ROM requires the
parsed page length to be greater than `0x0090` before accepting it, clears the
form-state block at `A8DA+`, stores the parsed length in `A8DA`, and initializes
`A8DC`, `A8DE`, and `A8E0` to `0x0048`. With perforation skip disabled, it stores
the page length and initializes those counters to zero.

`ESC v` sets top of form by resetting only the current form position: it writes
`A8E0 = 0x0000` when perforation skip is disabled and `A8E0 = 0x0048` when
perforation skip is enabled. It does not change the page length in `A8DA`.

Paper-out sensor commands (`ESC O` and `ESC o`) are hardware/status commands,
not layout commands. The manual-visible behavior is sensor off/on, and the ROM
entries are `0x30E1` and `0x30F0`; both toggle/test bits in the hardware/status
area (`VV:6B`, `VV:8B`) and then share the pending-output wait at `0x30E5`.
For PDF rendering, these can remain no-ops unless the emulator grows paper-out,
SheetFeeder auto-eject, error-light, or DTR/status modeling.

## Backspace And Overprint

`CTRL-H` is implemented as a lookahead overprint command, which matters for word
processors that compose glyphs by sending a base character, backspace, and an
accent or strike character.

Entry path:

| Address | Behavior |
| --- | --- |
| `0x274A` | Main loop compares the fetched byte with `0x08`; if equal, it calls `0x368C` before returning to the fetch loop. |
| `0x368C-0x3699` | Mode-gated validation/fetch path. In the normal path, it fetches the byte after `CTRL-H` with `CALT ($00B6)` and accepts bytes greater than `0x19` and less than `0x7F`; ordinary printable bytes are the important emulator case. Repeated `CTRL-H` bytes are skipped until a non-backspace is seen. |
| `0x36A4` | Saves the accepted post-backspace byte in `AA08`. |
| `0x36A8-0x36B3` | If current horizontal position `AA26` equals the left/base position `AA5E`, return without backing up. |
| `0x36B4-0x36D6` | Computes the accepted byte's rendered advance using `AA5A` and helper `0x3971`, then subtracts that advance from `AA26`. The result is bounded against `AA5E`. |
| `0x36DA-0x36E1` | Stores the backed-up position in `AA3C` and calls `CALT ($00A0)` (`0x275D`), which resets the active line position from `AA3C`. |
| `0x36E2-0x36E7` | Restores the saved byte from `AA08`, copies it to `C`, and jumps to default byte rendering at `0x28D7`. |

For emulator behavior, model `CTRL-H` as moving the next printable glyph back by
that glyph's current rendered advance and drawing it at the previous glyph's
position. Do not erase the previous glyph. The existing buffered line contents
and dot output should be OR/composited through the normal renderer.

This is not a simple fixed-column cursor-left operation. The ROM uses the
current pitch/width state when computing the backstep; double-width and
proportional modes therefore affect overprint placement. The left boundary is
`AA5E`, so backspace should not move before the current left margin/base
position.

## ESC Dispatch

The post-`ESC` command dispatcher starts at `0x2C07`.

Relevant code shape:

| Address | Meaning |
| --- | --- |
| `0x2C07` | Fetch command byte with `CALT ($00B6)`. |
| `0x2C08` | Load default handler `BC = 0x368B`. |
| `0x2C11-0x2C18` | Accept command bytes `0x21` through `0x7A`, subtract `0x21`, shift left, and execute `TABLE`. |
| `0x2C1A` | Branch back to `0x2C0E`, which `CALB`s the handler in `BC`. |
| `0x2C1B` | Start of the two-byte handler table. |
| `0x368B` | Common no-op/unsupported ESC handler. |

The uPD7810 `TABLE` instruction loads `BC` from `PC + A + 1`; it does not jump
by itself. Because execution continues at `0x2C1A`, the dispatch table and a
branch instruction intentionally overlap.

## Documented ESC Commands

| Command | Handler | Confidence | ROM notes |
| --- | ---: | --- | --- |
| `ESC !` | `0x2D15` | high | Sets an `AA5B` attribute bit; paired with `ESC "`. |
| `ESC "` | `0x2D18` | high | Clears the same `AA5B` attribute bit. |
| `ESC $` | `0x313E` | medium | Selects normal ROM font/path; handler alters `AA5B` font bits. |
| `ESC &` | `0x32E5` | medium | MouseText/alternate character-set mode bit path. |
| `ESC '` | `0x3163` | medium | Custom-character select path. |
| `ESC (` | `0x2E8D` | high | Horizontal tab set list. Uses `A9C0+` tab table and comma/period parser. |
| `ESC )` | `0x2E7A` | high | Horizontal tab clear list. Shares `A9C0+` tab table code. |
| `ESC *` | `0x3166` | medium | High-ASCII custom-character select path; interacts with `AA6B` bit `0x20`. |
| `ESC +` | `0x317E` | medium | Custom load mode path. |
| `ESC -` | `0x317B` | medium | Custom load mode path. |
| `ESC 0` | `0x2E9B` | high | Clears tab table via `0x3A15`. |
| `ESC 1` | `0x2D45` | high | Stores proportional spacing value `1` in `AA56`. |
| `ESC 2` | `0x2D47` | high | Stores proportional spacing value `2` in `AA56`. |
| `ESC 3` | `0x2D49` | high | Stores proportional spacing value `3` in `AA56`. |
| `ESC 4` | `0x2D4B` | high | Stores proportional spacing value `4` in `AA56`. |
| `ESC 5` | `0x2D4D` | high | Stores proportional spacing value `5` in `AA56`. |
| `ESC 6` | `0x2D4F` | high | Stores proportional spacing value `6` in `AA56`. |
| `ESC <` | `0x3241` | medium | Bidirectional/unidirectional bit path; paired with `ESC >`. |
| `ESC >` | `0x324B` | medium | Bidirectional/unidirectional bit path; paired with `ESC <`. |
| `ESC ?` | `0x3688` | high | Direct `JMP $217A`; `0x217A` stages and transmits `IW10...CR,NUL`. |
| `ESC A` | `0x32FF` | high | Sets `AA6D = 0x0018`, matching 6 lpi (`24/144`). |
| `ESC B` | `0x3306` | high | Sets `AA6D = 0x0012`, matching 8 lpi (`18/144`). |
| `ESC D` | `0x302A` | high | Software switch close/set. Reads two bytes, ORs masked bits into `AA6A/AA6B`. |
| `ESC E` | `0x2CE2` | high | Pitch/font mode handler; writes `AA5B` and `AA60`. |
| `ESC F` | `0x3283` | high | Parses four ASCII digits with `0x3FA8`; horizontal dot positioning with ROM range/rightward checks. |
| `ESC G` | `0x333A` | high | Graphics byte count parser; shares implementation with `ESC S`. |
| `ESC H` | `0x31F6` | high | Parses four ASCII digits with `0x3FA8`; stores page length in `A8DA` and initializes perforation-skip counters. |
| `ESC I` | `0x318F` | high | Custom character load path. Reads glyph data until `CTRL-D` (`0x04`). |
| `ESC K` | `0x2D27` | high | Reads ASCII digit `0`-`6` and stores color/ribbon selection in `AA7A`. |
| `ESC L` | `0x30B6` | high | Parses three ASCII digits with `0x3FA8`; left margin. |
| `ESC M` | `0x30F5` | high | Scribe font alias path; stores print-quality state through `AA70/AA71`. |
| `ESC N` | `0x2CDE` | high | Pitch mode; writes `AA5B` and `AA60`. |
| `ESC O` | `0x30E1` | high | Paper-out sensor off path; hardware/status side effect only for command-level rendering. |
| `ESC P` | `0x2CED` | high | Pitch mode; writes `AA5B` and `AA60`. |
| `ESC Q` | `0x2CE6` | high | Pitch mode; writes `AA5B` and `AA60`. |
| `ESC R` | `0x31CD` | high | Repeat-count parser. |
| `ESC S` | `0x333A` | high | Same graphics byte count path as `ESC G`. |
| `ESC T` | `0x3309` | high | Parses two ASCII digits with `0x3FA8`; sets line spacing through `AA6D`. |
| `ESC V` | `0x331A` | high | Graphics repeat command; four-digit count plus byte parameter. |
| `ESC W` | `0x2FFA` | high | Clears half-height state bits; paired with `ESC w`. |
| `ESC X` | `0x312C` | high | Sets underline attribute bit in `AA5B`. |
| `ESC Y` | `0x312F` | high | Clears underline attribute bit in `AA5B`. |
| `ESC Z` | `0x3065` | high | Software switch open/clear. Reads two bytes, ANDs masked bits out of `AA6A/AA6B`. |
| `ESC a` | `0x310D` | high | Reads ASCII `0`, `1`, or `2`; sets print-quality state through `AA70/AA71`. |
| `ESC c` | `0x31E3` | high | Software reset path; flush/wait then jumps to reset routine at `0x275D`. |
| `ESC e` | `0x2CF4` | high | Pitch mode; writes `AA5B` and `AA60`. |
| `ESC f` | `0x32F4` | high | Forward feed direction; stores `AA6C = 0x00`. Paired with `ESC r`. |
| `ESC g` | `0x332B` | high | Parses three ASCII digits and multiplies by eight for graphics count. |
| `ESC l` | `0x3251` | high | Reads ASCII `0`/`1`; toggles CR-before-LF/FF behavior. |
| `ESC m` | `0x3103` | high | Literal lowercase `m` aliases correspondence mode, matching `ESC a 0`. |
| `ESC n` | `0x2CF1` | high | Pitch mode; writes `AA5B` and `AA60`. |
| `ESC o` | `0x30F0` | high | Paper-out sensor on path; hardware/status side effect only for command-level rendering. |
| `ESC p` | `0x2CFD` | high | Pitch mode; writes `AA5B` and `AA60`. |
| `ESC q` | `0x2CFA` | high | Pitch mode; writes `AA5B` and `AA60`. |
| `ESC r` | `0x32FC` | high | Reverse feed direction; stores `AA6C = 0x04`. Paired with `ESC f`. |
| `ESC s` | `0x2E3D` | high | Reads one ASCII digit `0`-`9`; stores intercharacter spacing in `AA48`. |
| `ESC u` | `0x2E5A` | high | Add one tab stop; shares tab-table code. |
| `ESC v` | `0x3263` | high | Sets current form position `A8E0` to `0x0000` when perforation skip is disabled, or `0x0048` when it is enabled. |
| `ESC w` | `0x2FF1` | high | Sets half-height state bits; paired with `ESC W`. |
| `ESC x` | `0x3003` | high | Superscript state bits; paired with `ESC z`. |
| `ESC y` | `0x300E` | high | Subscript state bits; paired with `ESC z`. |
| `ESC z` | `0x3019` | high | Clears subscript/superscript state bits. |

## Common Helpers

| Helper | Purpose |
| --- | --- |
| `0x3FA8` | ASCII decimal parser. `B` gives digit count. Used by margins, page length, graphics counts, and tab commands. |
| `0x3D07` | Fetch one buffered byte and optionally mask to 7 bits depending on `AA6B bit 0x20`. |
| `0x3D79` | Printable-byte validator for custom-character load. It rejects control bytes and handles high-ASCII/custom ranges based on mode bits. |
| `0x3A15` | Clears a state/table block; used by tab reset and software reset paths. |
| `0x217A` | Builds and sends the self-ID response. |
| `0x23AE` | Emits `ESC K n` to the host/output stream; this is not the input handler for `ESC K`. |

## State Bytes And Defaults

The state names below are descriptive and should become emulator field names once
the last ambiguous bits are traced.

| Address | Bits/value | Current meaning | Evidence |
| --- | --- | --- | --- |
| `AA08` | byte | Saved post-backspace byte for overprint rendering. | `CTRL-H` handler `0x368C` stores the accepted lookahead byte at `0x36A4` and reloads it at `0x36E2` before jumping to `0x28D7`. |
| `AA26` | word | Current horizontal print position. | Tab handler `0x3718` advances it; renderer paths update it; `CTRL-H` subtracts a glyph advance from it when computing the overprint position. |
| `AA3C` | word | Line-start/current reset position used by shared line-position reset. | CR reset `0x3B19`, blank-line feed `0x3748`, and `CTRL-H` write this before paths that restore `AA26`. |
| `AA5B` | bit `0x01` | Underline enabled. | `ESC X`/`ESC Y` handlers `0x312C`/`0x312F` set/clear this bit. |
| `AA5B` | bit `0x02` | Bold enabled. | `ESC !`/`ESC "` handlers `0x2D15`/`0x2D18` set/clear this bit. |
| `AA5B` | bit `0x04` | Double-width text/graphics mode. | `0x370D` sets and `0x3706` clears this bit; control path reaches these routines for `CTRL-N`/`CTRL-O`. |
| `AA5B` | bits `0x38` | Pitch family selector. | `ESC N/E/Q/P/n/e/q/p` handlers mask `AA5B` with `0x07` and OR in `0x00`, `0x08`, `0x10`, `0x58`, `0x20`, `0x28`, `0x30`, or `0x78`. |
| `AA5E` | word | Left margin/base horizontal boundary. | Reset initializes it through `0x3A49`; `CTRL-H` refuses to back up when `AA26 == AA5E` and bounds computed backstep positions against it. |
| `AA60` | pointer | Font/metric base for current pitch. | Pitch handlers store `0x60C0`, `0x6088`, or `0x609E`. |
| `AA6A` | bits `0x01`, `0x02`, `0x04` | Software switches A-1 through A-3 / national character group bits. | `ESC D`/`ESC Z` first parameter is masked with `0xF7` and updates `AA6A`. |
| `AA6A` | bit `0x10` | Software select response disabled when set; enabled when clear. | `ESC D` sets and `ESC Z` clears documented A-5. `CTRL-S` at `0x37CB` only reaches deselect path `0x0449` when the bit is clear. |
| `AA6A` | bit `0x20` | Add LF when line is full. | Same `ESC D`/`ESC Z` mask; documented A-6 bit. |
| `AA6A` | bit `0x40` | Print trigger mode: CR-only vs CR/LF/FF. | Same `ESC D`/`ESC Z` mask; documented A-7 bit. |
| `AA6A` | bit `0x80` | Automatic LF after CR. | Same `ESC D`/`ESC Z` mask; documented A-8 bit. |
| `AA6B` | bit `0x01` | Slash-zero mode. | `ESC D`/`ESC Z` second parameter is masked with `0x25` and updates `AA6B`. |
| `AA6B` | bit `0x04` | Perforation skip disabled when set; enabled when clear. | Same second-parameter mask. `ESC D 00 04` sets it and zeroes/restores form counters; `ESC Z 00 04` clears it and initializes the skip offset to `0x0048`. |
| `AA6B` | bit `0x20` | Ignore eighth data bit when set; include it when clear. | `0x3D07` tests this bit and masks `A &= 0x7F` only when active. |
| `AA6C` | byte | Feed direction: `0x00` forward, `0x04` reverse. | `ESC f` stores `0x00`; `ESC r` stores `0x04`; vertical-feed record builders OR this value into their record type byte. |
| `AA6D` | word | Current line spacing in 1/144 inch units. | `ESC A` stores `0x0018`, `ESC B` stores `0x0012`, `ESC T` stores parsed value. |
| `AA70/AA71` | byte pair | Print-quality state/current target. | `ESC a` and `ESC M` write both bytes; helper `0x3CDB` compares them. |
| `AA7A` | byte | Ribbon/color selection. | `ESC K` writes transformed color digit at `0x2D39`; reset initializes it to `0x08`. |
| `AA48` | byte | Intercharacter spacing. | `ESC s` stores parsed digit at `0x2E4F`; reset clears it. |
| `AA56` | word | Extra proportional spacing accumulator/value. | `ESC 1`-`ESC 6` store values `1`-`6`; reset clears it. |
| `A8DA` | word | Page length in 1/144 inch units. | Reset stores `0x0630` or `0x06C0` from SW1-4; `ESC H nnnn` stores the parsed page length here. |
| `A8DC/A8DE` | words | Perforation-skip offsets/counters. | Reset, `ESC H`, and `ESC D/Z ... 04` maintain these as `0x0048` when perforation skip is enabled or zero/restored values when disabled. |
| `A8E0` | word | Current form position used by the feed scheduler. | Reset and `ESC H` initialize it; `ESC v` writes only this word; lower-level feed routines compare/update it. |
| `A8E2` | word | Saved/default line spacing for form logic. | Reset stores `0x0018`, matching default `AA6D`. |
| `A8E4` | word | Saved perforation-skip/form baseline. | Reset copies the initialized perforation-skip value here; `ESC D 00 04` copies it back to `A8DE` when disabling skip. |
| `A9C0+` | table | Horizontal tab stop table. | `ESC (`/`)`/`0`/`u` handlers operate on this region through `A9B6`, `A9B8`, and `A9BD`. |

Default setup is centered at `0x3989`:

- `0x3A51` initializes `AA6A` and `AA6B` from DIP switch shadow `FF00`.
- `0x3A70` initializes pitch/color-related state (`AA5A`, `AA58`, `AA7A`) from
  the SW1 pitch bits.
- `0x39DB` sets print quality state (`AA70/AA71 = 2`), clears intercharacter
  spacing (`AA48 = 0`), clears extra proportional spacing (`AA56 = 0`), and sets
  default line spacing (`AA6D = 0x0018`).
- `0x3A15` clears the tab table block at `A9B6+`.

## Graphics And Custom Characters

Graphics commands share most of their implementation:

| Command | Handler path | ROM behavior still to model |
| --- | --- | --- |
| `ESC G nnnn` / `ESC S nnnn` | `0x333A -> 0x3340+` | Parses a four-digit byte count with `0x3FA8`, then repeatedly consumes graphics bytes. |
| `ESC g nnn` | `0x332B -> 0x3331 -> 0x3340+` | Parses three digits, shifts left three times, then uses the same graphics byte path. |
| `ESC V nnnn c` | `0x331A -> 0x3320+` | Parses a four-digit repeat count and stores the repeated byte in `AA78`. |
| `ESC F nnnn` | `0x3283 -> 0x3289+` | Parses a four-digit dot-column position, bounds it against a width table at `0x46CE`, and updates the horizontal print position only when the target is strictly right of the current position. |

The shared graphics path uses `AA09`, `AA2C/AA2E`, `AA32/AA34/AA38`,
`AA44`, `AA78`, and `AA7E`. Graphics bytes use the same bit order as custom
characters: bit 0 fires the top wire and bit 7 fires the bottom wire of the top
eight-wire graphics column. Double-width mode accepts half the normal number of
bytes per line and prints two identical dot columns for each graphics data byte.
Bold mode prints each graphics dot twice with a small horizontal shift.

`ESC F` trace details:

| Address | Behavior |
| --- | --- |
| `0x3283-0x3288` | Sets `B = 4` and calls the shared ASCII decimal parser `0x3FA8`. Parser spaces are treated as zeroes. |
| `0x3289-0x329B` | Masks `AA5B` pitch-family bits with `0x38`, shifts right twice, and uses the result as an even byte offset into the little-endian bounds table at `0x46CE`. |
| `0x329B-0x329E` | Compares requested `nnnn` against the table value. If the table value is less than the request, the handler returns without moving. |
| `0x329F-0x32CB` | Converts the accepted dot column into the current horizontal position units and adds the left-margin/base position `AA5E`. |
| `0x32CF-0x32D6` | Compares the current horizontal position `AA26` with the target and returns unless the target is strictly to the right. |
| `0x32D7-0x32E2` | Stores the target in `AA26` and queues the horizontal skip/positioning side effect through `0x3E10`. |

The bounds table is indexed by the pitch bits in `AA5B`:

| Pitch command | `AA5B & 0x38` | Table value | Accepted `ESC F` columns |
| --- | ---: | ---: | ---: |
| `ESC N` pica | `0x00` | `639` | `0000`-`0639` |
| `ESC E` elite | `0x08` | `767` | `0000`-`0767` |
| `ESC Q` ultracondensed | `0x10` | `1087` | `0000`-`1087` |
| `ESC P` proportional elite | `0x18` | `1279` | `0000`-`1279` |
| `ESC n` extended | `0x20` | `575` | `0000`-`0575` |
| `ESC e` semicondensed | `0x28` | `855` | `0000`-`0855` |
| `ESC q` condensed | `0x30` | `959` | `0000`-`0959` |
| `ESC p` proportional pica | `0x38` | `1151` | `0000`-`1151` |

Custom-character loading is anchored at `ESC I` handler `0x318F`. The ROM and
manual agree that this is a repeated record stream, not an arbitrary byte run:

```text
ESC - ESC I key width data[width] ... CTRL-D
ESC + ESC I key width data[width] ... CTRL-D
```

Trace details:

| Address | Behavior |
| --- | --- |
| `0x317B` / `0x317E` | `ESC -` / `ESC +` select 8-dot or 16-dot maximum-width load mode, wait for the output path, then clear downloaded-character RAM at `A200..A85F` (`0x0660` bytes). |
| `0x3195` | Fetches the first target `key` byte through `CALT ($00A4)`. |
| `0x3196-0x319B` | Calls validator `0x3D79`; invalid target bytes abort the load command. |
| `0x319C-0x31A0` | Loads the active metric/mode table pointer from `AA5A` and calls `0x31BC` to compute the destination slot. |
| `0x31A4-0x31AB` | Calls `0x3D96` to fetch and validate the width code, then stores that byte as slot byte 0. |
| `0x31AC-0x31B5` | Copies exactly the width-code-selected number of bitmap bytes into following slot bytes. |
| `0x31B6-0x31BB` | Fetches the next byte. If it is `CTRL-D` (`0x04`), the load command returns; otherwise that byte is treated as the next target `key` and validation resumes at `0x3196`. |
| `0x3958-0x396C` | Render path recomputes the custom slot, reads slot byte 0, masks it with `0x1F`, and uses that as rendered width. Bitmap columns start at slot byte 1. |

The documented width codes are `A` through `P` for top-eight-wire glyphs and
`a` through `p` for bottom-eight-wire glyphs. The low five bits give the number
of following bitmap bytes (`1..16`). Each bitmap byte uses bit 0 for the top
wire and bit 7 for the bottom of the selected 8-wire group.

Target-key constraints from the manual and `0x3D79`:

- Ordinary custom characters are assigned to printable ASCII keys `0x20..0x7E`.
- In 8-dot maximum-width mode, high-ASCII custom characters may also be assigned
  to `0xA0..0xEF`, giving the documented 95 ordinary plus 80 high-ASCII slots.
- In 16-dot maximum-width mode, only the ordinary printable set is available,
  matching the documented 95-character capacity.
- `ESC *` prints high-ASCII custom characters by accepting standard ASCII
  `0x20..0x6F` and adding `0x80`, so it reaches high custom assignments
  `0xA0..0xEF`.

This means `CTRL-D` is not a global control command in the normal command table;
it is meaningful at the next-target position inside the custom-character loader.

## Documentation Corrections And Interactions

- Literal lowercase `ESC m` (`1B 6D`) is a font alias handled at `0x3103`.
  Proportional spacing `ESC 1` through `ESC 6` is handled separately at
  `0x2D45-0x2D4F`. These are not the same command.
- Uppercase `ESC O` (`0x4F`) and lowercase `ESC o` (`0x6F`) are distinct
  entries at `0x30E1` and `0x30F0`.
- `ESC l0`/`ESC l1` uses lowercase ell (`0x6C`), implemented at `0x3251`.
- `ESC D` and `ESC Z` are true bitmask operations, not enumerated special cases.
  The first parameter updates `AA6A` with mask `0xF7`; the second updates `AA6B`
  with mask `0x25`.
- `ESC ?` is available in this ROM as a direct table entry to `0x3688`, which
  jumps to the self-ID builder at `0x217A`.
- `0x41AD` compares a decoded glyph/control metric against `0x1B`; it is not the
  raw ESC command parser.
- `0x23AE` can be mistaken for the `ESC K` input handler because it emits bytes
  `1B 4B n`. The real input handler is `0x2D27`.
