# Target: google-photos

The default target of `lightcraft-export`. Photos go into a folder that **Google Drive for desktop**
backs up to Google Photos. There is no Google Photos connector, and the skill never uploads or signs in.

## Settings

Options checked against the `app.export` schema of LightCraft 0.21 (an unknown option is an error, not
ignored):

| What | Option | Why |
|---|---|---|
| Format | `format=jpeg` | Google Photos stores JPEG anyway. A PNG is 5–10 times larger and looks the same there |
| Size | `mp=16` → `megapixels=16 dontEnlarge=true` | Storage saver recompresses anything above 16 MP; at or under 16 MP it is not resized again, whatever the aspect ratio or crop |
| Size, GPU rendering on (entry-level GPU) | `edge=4000` → `longEdge=4000 dontEnlarge=true` | the edit skill's GPU limit |
| Quality | `quality=92` | |
| Colour | `colorSpace=srgb` | Google Photos and phones show sRGB |
| Sharpening | `sharpen=screen sharpenAmount=low` | output sharpening for screens; more brings the grain back |
| Metadata | `metadata=all` | keeps the capture date (Photos sorts by it) and GPS (the map) |

App-export options for `export-stage.sh`:
`format=jpeg quality=92 colorSpace=srgb sharpen=screen sharpenAmount=low metadata=all`

Preference keys (defaults):
- `export.google-photos.root`: the folder Drive for desktop backs up, e.g. `D:/Photos/GooglePhotos` (no default; ask).
- `export.google-photos.staging`: default `<parent of root>/.lc-staging`.
- `export.google-photos.min_rating`, `export.google-photos.people`: override the shared keys.

## Destination

`<root>/<trip folder>/`, e.g. `D:/Photos/GooglePhotos/2026-11 Japan/`. Drive for desktop uploads new
files on its own, and Storage saver applies to them.

## Naming

The camera's file name (`DSC01234.jpg`). It becomes `DSC01234-<id>.jpg` when that name is taken
in the batch or in the folder, or when the photo is a forced re-export. Files are never overwritten.

## Limits

- Storage saver: 16 MP. Original quality: the file is kept as it is, but counts against storage.
- Google Photos: at most 200 MB and 200 MP per photo (a 16 MP JPEG is 2–8 MB).
- Drive for desktop uploads a file **again** if it is replaced or renamed in the folder. Hence the
  skill's no-overwrite rule.

## One-time setup (the user does this)

1. Install Google Drive for desktop and sign in.
2. Settings → My Computer → Add folder → choose `export.google-photos.root` → **Back up to Google
   Photos** (not "Sync with Google Drive").
3. Google Photos upload size: **Storage saver**.
4. Keep the staging folder (`.lc-staging`) **out** of the backed-up folders.

## Checks (on 3 sample files, with Pillow: `"$LC_PY" -E -c ...`)

- `width × height ≤ 16 000 000 × 1.005` (or a long edge ≤ 4000 with `edge=4000`).
- An ICC profile is present (sRGB).
- EXIF `DateTimeOriginal` (tag 36867 in the Exif IFD) is present. Check GPS (IFD 34853) on a photo that
  has GPS in the catalog: run `photo.allMetadata id=N` first to see whether the original has it.
- If a check fails, stop and tell the user before exporting more photos.

## After (the user does this)

- Check that Drive for desktop has finished uploading (its tray icon shows the upload).
- In Google Photos, make the trip album from the uploaded photos (Drive does not create albums).
- For a forced re-export, delete the old copy in Google Photos.
