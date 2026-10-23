Test data files downloaded from:
https://sembiance.com/fileFormatSamples/archive/crunchMania/

These are Crunch-Mania compressed files from the Amiga era, covering all four
format variants:

- `CrM!` - Normal mode: `031`, `test_C1.crm`
- `CrM2` - LZH mode: `13.bmp.crm2`, `14.bmp`, `15.bmp`, `5.bmp`, `6.bmp`,
  `DECK2prefs`, `GAME-OVER.DAWN`, `pubfinale1`, `test_C1_lz.crm`, `vdp15`
- `Crm!` - Normal mode + delta: `test_C1_delta.crm`
- `Crm2` - LZH mode + delta: `shnock`, `test_C1_lz_delta.crm`

`sha256.json` records SHA-256 hashes of the decompressed valid fixtures,
independently generated using Ancient 2.3.0. These checks run even when the
reference executable is unavailable.
