# ImageWriter II Command Reference

This file extracts the emulation-relevant command set from the Apple ImageWriter II Technical Reference Manual and Owner's Manual. It normalizes obvious OCR errors in the PDFs: escape is `1B`, uppercase `O` is `4F`, lowercase `o` is `6F`, and the letter `l` in `ESC l0`/`ESC l1` is lowercase ell (`6C`), not digit one.

Byte notation:

- `ESC` = `1B`
- `CTRL-@` = `00`
- Decimal digit parameters are ASCII digits unless explicitly noted.
- Numeric parameters named `nnn`/`nnnn` are sent as ASCII decimal digits, not binary integers, unless noted otherwise.

## Behavioral Model

The printer buffers text and most commands until a print trigger is reached. By default, carriage return (`0D`), line feed (`0A`), and form feed (`0C`) cause the current print buffer to be printed. Software switch A-7 can restrict printing to carriage return only.

Many `ESC D a b` and `ESC Z a b` commands operate on software-switch bits. `ESC D` closes/sets the selected bits; `ESC Z` opens/clears the selected bits. The user-visible meaning is bit-specific, so these are state mutations, not rendering commands.

Control bytes `00`-`1F` are command bytes in the normal path. Their high-bit
counterparts `80`-`9F` depend on the B-6 eighth-bit switch: with the eighth bit
ignored they collapse to `00`-`1F`; with the eighth bit included they can remain
high-ASCII character/custom-character inputs rather than control actions.

## Control Characters

| Bytes | Mnemonic | Class | Effect |
| --- | --- | --- | --- |
| `07` | `CTRL-G` | alert/control | Literal `0x07` does not print a glyph. High-bit `0x87` is separate: it aliases to `0x07` when the eighth bit is ignored, but can print the ROM high-ASCII glyph when the eighth bit is included. |
| `08` | `CTRL-H` | print-head motion | Backspace one character. Enables overprinting; the following glyph is printed over the previous position rather than erasing it. |
| `09` | `CTRL-I` | print-head motion | Horizontal tab to next tab stop. |
| `0A` | `CTRL-J` | paper motion / print trigger | Line feed one line. Default also prints buffered line. |
| `0B` | `CTRL-K` | paper motion / undocumented | ROM-observed vertical-tab-like feed path at `0x37A4`; not found in the extracted manual command list. |
| `0C` | `CTRL-L` | paper motion / print trigger | Form feed to next top of form. Default also prints buffered line. |
| `0D` | `CTRL-M` | print-head motion / print trigger | Carriage return. |
| `0E` | `CTRL-N` | text attribute / graphics | Start double-width printing. Also doubles graphics dots. |
| `0F` | `CTRL-O` | text attribute / graphics | Stop double-width printing. |
| `11` | `CTRL-Q` | selection | Select printer, if software select response is enabled. |
| `13` | `CTRL-S` | selection | Deselect printer, if software select response is enabled. |
| `18` | `CTRL-X` | buffer control | Erase the current not-yet-printed line from the print buffer. Does not print or feed paper. |
| `1D` | `CTRL-]` | undocumented vertical-format/setup command | ROM-observed parser at `0x37D7`. It accepts `CTRL-] A@ {even-byte@...} A@ trailer`, stores one byte per row at `A955+`, and derives a form length from current line spacing. The trailer byte is consumed; `0x1E` enters a non-returning firmware loop. |
| `1F n` | `CTRL-_ n` | paper motion | Feed `n` blank lines, where `n` is ASCII `1` through `9`, `:`, `;`, `<`, `=`, `>`, or `?` for 1-15 lines. |

Other low controls fall through the ROM's default byte path rather than the keyed
control table. With the eighth-bit switch set to ignore bit 7, high-bit bytes
`80`-`9F` collapse to these controls; with bit 7 included, they can instead be
treated as high-ASCII/custom-character input.

`CTRL-G` follows that rule. The literal byte `0x07` is below the printable
threshold in the default byte path and is not rendered. The byte `0x87` reaches
the high-ASCII path only when the eighth-bit switch is set to include bit 7.

The ROM implements `CTRL-H` by looking at the byte that follows it and rendering
that byte at the backed-up position. For emulation, this is equivalent to a
non-destructive backspace state: `A 08 accent` should leave the `A` dots in the
line buffer and compose the accent through the normal renderer.

`CTRL-X` acts when it is consumed from the buffered input stream. For example,
`ABC 18 DEF 0D` prints only `DEF`; `ABC 0D 18 DEF 0D` cannot erase the already
printed `ABC`.

## Print Quality

| Bytes | Command | Class | Effect | Default |
| --- | --- | --- | --- | --- |
| `1B 61 30` | `ESC a 0` | font | Correspondence font. | |
| `1B 61 31` | `ESC a 1` | font | Draft font. | hard/soft reset |
| `1B 61 32` | `ESC a 2` | font | Near letter quality font. | |
| `1B 6D` | `ESC m` | font alias | Same as `ESC a 0` for Scribe compatibility. This is literal lowercase `m` (`6D`). | |
| `1B 4D` | `ESC M` | font alias | Same as `ESC a 2` for Scribe compatibility. | |

Draft font does not support bold, double-width, half-height, subscript, superscript, or proportional printing. Selecting one of those modes while in draft temporarily switches to correspondence.

ROM trace note: `ESC a`/`ESC m`/`ESC M` feed requested quality through the
`AA70/AA71` mechanism. `3CDB` (entered from the printable-byte consume path) can
clamp quality at render time, so the request is not always applied immediately.

## Character Sets

| Bytes | Command | Class | Effect | Default |
| --- | --- | --- | --- | --- |
| `1B 26` | `ESC &` | character set | Map MouseText to low ASCII `$40-$5F`. | |
| `1B 24` | `ESC $` | character set | Select standard ASCII / normal ROM font. | hard/soft reset |
| `1B 5A 00 20` | `ESC Z CTRL-@ SPACE` | software switch | Include eighth data bit. | |
| `1B 44 00 20` | `ESC D CTRL-@ SPACE` | software switch | Ignore eighth data bit. | hard/soft reset |
| `1B 27` | `ESC '` | custom font | Select custom-character font for normal ASCII assignments. | |
| `1B 2A` | `ESC *` | custom font | Select custom-character font for high-ASCII assignments via low-ASCII aliases. | |
| `1B 2D` | `ESC -` | custom load mode | Custom characters max width 8 dots; clears loaded custom characters and enables 8-bit data. | default |
| `1B 2B` | `ESC +` | custom load mode | Custom characters max width 16 dots; clears loaded custom characters and enables 8-bit data. | |
| `1B 49` | `ESC I` | custom load | Begin loading one or more `key width data...` custom-character records. | |
| `04` | `CTRL-D` | custom load | End custom-character loading when read where the next `key` byte would appear. | |

ROM trace notes for emulation:

- `ESC $`, `ESC &`, `ESC '`, and `ESC *` are mutually exclusive
  character-source selections at the command level: normal ROM font,
  MouseText aliases, ordinary custom characters, and high custom-character
  aliases respectively.
- `ESC &` maps low ASCII `0x40..0x5F` onto MouseText glyphs. It is not layered
  on top of the custom-character selectors.
- `ESC '` selects custom characters assigned to their normal printable keys.
- `ESC *` selects high custom-character aliases by accepting low ASCII
  `0x20..0x6F` and adding `0x80`, so those bytes print custom slots
  `0xA0..0xEF` when defined.
- `ESC -` and `ESC +` choose the maximum custom-character load width, clear
  downloaded-character RAM, and enable eight-bit data. They do not by
  themselves select the custom font for printing.

National character groups are selected through software switches A-1 through A-3:

| Language | Bytes |
| --- | --- |
| American | `1B 5A 07 00` |
| Italian | `1B 5A 06 00 1B 44 01 00` |
| Danish | `1B 5A 05 00 1B 44 02 00` |
| British | `1B 5A 04 00 1B 44 03 00` |
| German | `1B 5A 03 00 1B 44 04 00` |
| Swedish | `1B 5A 02 00 1B 44 05 00` |
| French | `1B 5A 01 00 1B 44 06 00` |
| Spanish | `1B 44 07 00` |

## Pitch And Spacing

| Bytes | Command | Class | Effect | Default |
| --- | --- | --- | --- | --- |
| `1B 6E` | `ESC n` | pitch | 9 cpi extended, 72 chars/line. | |
| `1B 4E` | `ESC N` | pitch | 10 cpi pica, 80 chars/line. | DIP SW1-6/SW1-7 can select |
| `1B 45` | `ESC E` | pitch | 12 cpi elite, 96 chars/line. | DIP SW1-6/SW1-7 can select |
| `1B 65` | `ESC e` | pitch | 13.4 cpi semicondensed, 107 chars/line. | |
| `1B 71` | `ESC q` | pitch | 15 cpi condensed, 120 chars/line. | |
| `1B 51` | `ESC Q` | pitch | 17 cpi ultracondensed, 136 chars/line. | DIP SW1-6/SW1-7 can select |
| `1B 70` | `ESC p` | proportional pitch | 144 dpi pica proportional. | |
| `1B 50` | `ESC P` | proportional pitch | 160 dpi elite proportional. | DIP SW1-6/SW1-7 can select |
| `1B 73 n` | `ESC s n` | proportional spacing | Set intercharacter spacing to `n` dots, ASCII `0`-`9`. | `0` |
| `1B 31`-`1B 36` | `ESC m` where `m` is `1`-`6` | proportional spacing | Insert `m` extra dot spaces; cumulative. This uses ASCII digit bytes, not literal lowercase `m`. | |

## Text Attributes

| Bytes | Command | Class | Effect | Default |
| --- | --- | --- | --- | --- |
| `1B 58` | `ESC X` | underline | Start underline. | |
| `1B 59` | `ESC Y` | underline | Stop underline. | hard/soft reset |
| `1B 21` | `ESC !` | bold | Start boldface. | |
| `1B 22` | `ESC "` | bold | Stop boldface. | hard/soft reset |
| `1B 77` | `ESC w` | half-height | Start half-height text. | |
| `1B 57` | `ESC W` | half-height | Stop half-height text. | hard/soft reset |
| `1B 78` | `ESC x` | script | Start superscript. | |
| `1B 79` | `ESC y` | script | Start subscript. | |
| `1B 7A` | `ESC z` | script | Stop subscript/superscript. | hard/soft reset |
| `1B 44 00 01` | `ESC D CTRL-@ CTRL-A` | software switch | Slash zeros. | |
| `1B 5A 00 01` | `ESC Z CTRL-@ CTRL-A` | software switch | Do not slash zeros. | hard/soft reset |

## Page Formatting And Print-Head Motion

| Bytes | Command | Class | Effect | Default |
| --- | --- | --- | --- | --- |
| `1B 4C n n n` | `ESC L nnn` | page format | Set left margin at column `nnn`. | `000` |
| `1B 48 n n n n` | `ESC H nnnn` | page format | Set page length to `nnnn/144` inch, range `0001`-`9999`. | DIP SW1-4 |
| `1B 3E` | `ESC >` | print direction | Unidirectional printing. | |
| `1B 3C` | `ESC <` | print direction | Bidirectional printing. | hard/soft reset |
| `1B 28 ... 2E` | `ESC ( aaa,bbb,...,nnn.` | tabs | Set horizontal tab stops. ASCII decimal columns separated by commas and terminated with period. | cleared |
| `1B 75 n n n` | `ESC u nnn` | tabs | Add one tab stop at column `nnn`. | |
| `1B 29 ... 2E` | `ESC ) aaa,bbb,...,nnn.` | tabs | Clear selected horizontal tab stops. | |
| `1B 30` | `ESC 0` | tabs | Clear all horizontal tabs. | cleared |
| `1B 46 n n n n` | `ESC F nnnn` | print-head motion / graphics | Place print head `nnnn` dot columns from left margin, only if the target is to the right of the current head position. | |

Print direction is a property of the print pass, not of each byte as it is
received. A pending line should use the `ESC <`/`ESC >` mode in effect when
the line or partial line is actually printed. `ESC >` forces left-to-right
printing. `ESC <` permits alternating bidirectional text and graphics passes.

## Paper Motion

| Bytes | Command | Class | Effect | Default |
| --- | --- | --- | --- | --- |
| `1B 41` | `ESC A` | line spacing | 6 lines per inch. | hard/soft reset |
| `1B 42` | `ESC B` | line spacing | 8 lines per inch. | |
| `1B 54 n n` | `ESC T nn` | line spacing | Line spacing `nn/144` inch, range `01`-`99`. | |
| `1B 66` | `ESC f` | feed direction | Forward line feed. | hard/soft reset |
| `1B 72` | `ESC r` | feed direction | Reverse line feed. | |
| `1B 76` | `ESC v` | top of form | Set current position as top of form. | |
| `1B 44 00 04` | `ESC D CTRL-@ CTRL-D` | software switch | Disable perforation skip. | depends on SW1-5 |
| `1B 5A 00 04` | `ESC Z CTRL-@ CTRL-D` | software switch | Enable perforation skip. | depends on SW1-5 |
| `1B 4F` | `ESC O` | sensor | Paper-out sensor off. | |
| `1B 6F` | `ESC o` | sensor | Paper-out sensor on. | hard/soft reset |

ROM-observed paper/form interactions:

- Paper motion is queued as vertical-feed records; command handlers do not drive
  the stepper motor directly. `ESC f` and `ESC r` set the direction byte used by
  later `LF`, `FF`, blank-line, and auto-feed records.
- Page length and feed distances use 1/144 inch units. The hard-reset default is
  11 inches (`0x0630`) or 12 inches (`0x06C0`) from SW1-4; default line spacing
  is 6 lpi (`0x0018`).
- `ESC D 00 04` disables perforation skip. In ROM state this sets
  `AA6B bit 0x04`, clears the active skip/current-form offsets, and restores one
  saved form baseline.
- `ESC Z 00 04` enables perforation skip. In ROM state this clears
  `AA6B bit 0x04` and uses a half-inch skip offset (`0x0048`, or 72/144 inch).
- `ESC H nnnn` stores the page length and reinitializes the form counters. With
  perforation skip enabled, the ROM accepts only lengths greater than `0x0090`.
- `ESC v` sets top of form by resetting the current form-position word only; it
  does not change the stored page length.

## Automatic CR/LF Behavior

| Bytes | Command | Class | Effect | Default |
| --- | --- | --- | --- | --- |
| `1B 6C 31` | `ESC l 1` | CR insertion | No CR inserted before LF/FF. | |
| `1B 6C 30` | `ESC l 0` | CR insertion | Insert CR before LF/FF. | hard/soft reset |
| `1B 44 80 00` | `ESC D high-CTRL-@ CTRL-@` | software switch | Add automatic LF after CR. | depends on SW1-8 |
| `1B 5A 80 00` | `ESC Z high-CTRL-@ CTRL-@` | software switch | No automatic LF after CR. | depends on SW1-8 |
| `1B 44 20 00` | `ESC D SPACE CTRL-@` | software switch | Add LF when line is full. | |
| `1B 5A 20 00` | `ESC Z SPACE CTRL-@` | software switch | No LF when line is full. | hard/soft reset |

When a printable byte would overflow a full line, the firmware treats the full
line as a print trigger and forces the horizontal position back to the left
margin before retrying that same byte. The byte is not discarded and is not
overstruck in the last column.

The vertical feed part of this overflow handling is controlled only by A-6
(`ESC D SPACE CTRL-@` / `ESC Z SPACE CTRL-@`). With the hard-reset default
`ESC Z SPACE CTRL-@`, the printer does not feed paper on full-line overflow, so
the retried byte starts at the left edge of the same physical line. This is not
the same as inserting a host `CR`: A-8 controls LF-after-CR, while A-6 controls
LF-on-full-line. `ESC l0`/`ESC l1` affects explicit LF/FF handling and is not
part of printable-byte overflow.

## Graphics

| Bytes | Command | Class | Effect |
| --- | --- | --- | --- |
| `1B 47 n n n n` | `ESC G nnnn` | bit image | Print one graphics line from the following `nnnn` bytes. |
| `1B 53 n n n n` | `ESC S nnnn` | bit image | Same as `ESC G`. |
| `1B 67 n n n` | `ESC g nnn` | bit image | Print graphics from following `nnn * 8` bytes. |
| `1B 56 n n n n c` | `ESC V nnnn c` | graphics repeat | Repeat dot column byte `c` `nnnn` times. |
| `1B 46 n n n n` | `ESC F nnnn` | graphics positioning | Begin printing at dot column `nnnn` from left margin, only if the target is to the right of the current head position. |

Graphics data uses the top eight print wires. Bit 0 prints the top dot in a
graphics column and bit 7 prints the bottom dot. Double-width mode (`CTRL-N`)
prints two identical columns for each graphics byte, so the maximum accepted
bytes per line is halved. Boldface is also available in graphics modes.

Graphics bytes are interpreted in logical left-to-right column order. Physical
print-head direction is still controlled by `ESC <`/`ESC >`: in bidirectional
mode a graphics line can print on either pass, while `ESC >` forces the pass to
left-to-right for better vertical alignment.

ROM-observed `ESC F` details:

- The four parameter bytes are ASCII decimal digits; spaces are accepted as
  zeroes by the shared numeric parser.
- Positions are zero-based dot columns from the current left margin. The ROM
  ignores the command when `nnnn` is beyond the current pitch's printable width
  or when the target is not strictly to the right of the current head position.
- The accepted range is `0000` through the maximum below. This is one less than
  the manual's dot-count table because column zero is a valid position.

| Pitch mode | Horizontal density | Accepted `ESC F` columns |
| --- | ---: | ---: |
| Pica (`ESC N`) | 80 dpi | `0000`-`0639` |
| Elite (`ESC E`) | 96 dpi | `0000`-`0767` |
| Ultracondensed (`ESC Q`) | 136 dpi | `0000`-`1087` |
| Proportional elite (`ESC P`) | 160 dpi | `0000`-`1279` |
| Extended (`ESC n`) | 72 dpi | `0000`-`0575` |
| Semicondensed (`ESC e`) | 107 dpi | `0000`-`0855` |
| Condensed (`ESC q`) | 120 dpi | `0000`-`0959` |
| Proportional pica (`ESC p`) | 144 dpi | `0000`-`1151` |

## Color

| Bytes | Command | Class | Effect | Default |
| --- | --- | --- | --- | --- |
| `1B 4B 30` | `ESC K 0` | color | Black. | hard/soft reset |
| `1B 4B 31` | `ESC K 1` | color | Yellow. | |
| `1B 4B 32` | `ESC K 2` | color | Magenta. | |
| `1B 4B 33` | `ESC K 3` | color | Cyan. | |
| `1B 4B 34` | `ESC K 4` | color | Orange, yellow plus magenta. | |
| `1B 4B 35` | `ESC K 5` | color | Green, yellow plus cyan. | |
| `1B 4B 36` | `ESC K 6` | color | Purple/violet, magenta plus cyan. | |

The Apple manual describes the four physical ribbon bands as yellow, cyan
("greenish-blue"), magenta ("purplish-red"), and black. Orange, green, and
purple are documented as color combinations; the manual notes that other printer
manuals often call those orange and purple combinations "red" and "blue."
The ROM stores the selected color as a ribbon mask in `AA7A`: black is `0x08`,
yellow `0x01`, magenta `0x02`, cyan `0x04`, orange `0x03`, green `0x05`, and
purple `0x06`. Emulator RGB values are approximations, sanity-checked against
public scans but not calibrated against known ribbon samples. The service
manuals' self-test names the same physical sequence as black, yellow, red,
blue, orange, green, and purple; in that context red is magenta and blue is
cyan.

Treat `ESC K 4`, `ESC K 5`, and `ESC K 6` as single command selections whose
mask contains two primary ribbon bits: orange is yellow plus magenta, green is
yellow plus cyan, and purple/violet is magenta plus cyan. Render those masks as
component ink deposits, not as invented fifth/sixth/seventh physical ribbon
bands. The physical printer must position one ribbon band, print the buffered
dots, then position the other band and overprint the same dot coordinates; there
is no orange, green, or violet ribbon-motor state.

The ROM's print setup path decomposes a combined mask by extracting the lowest
set component bit first, storing the remaining bits for a later pass
(`0x0CA1-0x0D29`, followed by the repeat path through `0x151C`). That makes the
component order yellow then magenta for orange, yellow then cyan for green, and
magenta then cyan for purple/violet. Apple's manual's yellow-first advice
therefore matches the ROM behavior for yellow-bearing combinations; purple's
magenta-then-cyan order comes from the ROM bit extraction rather than from a
manual statement. That order matters only if the emulator models ribbon
contamination or pass-timing artifacts; for normal page compositing,
purple/violet is the cumulative result of both component deposits at the same
coordinates.
For dot rendering, each component deposit should use the normal pin-strike
kernel independently. That means a secondary color selection gets two deposits
at the same nominal dot coordinate, with the renderer's usual radius, density,
and placement variation applied to each component.

Explicit overprinting is also cumulative: software can print one color, return
to the same vertical position, and print another color over it. An emulator
should accumulate those strikes into the page image rather than treating the
later color as replacing the earlier one.

## Miscellaneous

| Bytes | Command | Class | Effect | Default |
| --- | --- | --- | --- | --- |
| `1B 5A 40 00` | `ESC Z @ CTRL-@` | software switch | Only CR causes printing. | |
| `1B 44 40 00` | `ESC D @ CTRL-@` | software switch | CR, LF, and FF cause printing. | hard/soft reset |
| `1B 52 n n n c` | `ESC R nnn c` | repetition | Repeat printable character `c`, `nnn` times, range `001`-`999`. Spaces may replace leading zeroes. |
| `1B 63` | `ESC c` | reset | Software reset. Prints previous buffered data first; can take up to about 3 seconds. | |
| `1B 44 10 00` | `ESC D CTRL-P CTRL-@` | software switch | Disable software select response. | hard/soft reset |
| `1B 5A 10 00` | `ESC Z CTRL-P CTRL-@` | software switch | Enable software select response. | |
| `1B 3F` | `ESC ?` | query | Send self-ID string. Not available through AppleTalk option. | |

## DIP And Software Switch Summary

Hard reset takes SW1 language, page length, perforation skip, pitch, and LF-after-CR defaults from DIP switches. SW2 controls baud, protocol, option card enable, and factory hammer timing; SW2 has no software equivalents.

Software-switch bit meanings:

| Bit | `ESC Z` open/off | `ESC D` closed/on | Default |
| --- | --- | --- | --- |
| A-1 | SW1-1 open | SW1-1 closed | DIP |
| A-2 | SW1-2 open | SW1-2 closed | DIP |
| A-3 | SW1-3 open | SW1-3 closed | DIP |
| A-5 | Software select response enabled | Software select response disabled | disabled |
| A-6 | No LF when line full | Add LF when line full | no LF |
| A-7 | CR only prints | CR, LF, FF print | CR/LF/FF |
| A-8 | CR only | CR plus LF | DIP |
| B-1 | Do not slash zero | Slash zero | unslashed |
| B-3 | Perforation skip enabled | Perforation skip disabled | DIP |
| B-6 | Include eighth data bit | Ignore eighth data bit | ignore |
