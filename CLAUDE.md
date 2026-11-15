# Project: Mover Spotter (NASA Space Apps 2026, "Planet X and SPHEREx")

Put this file in the project root as `CLAUDE.md`. It is the full context from the planning chat.

## Deadline and constraints
- Hackathon, must be finished in about ONE day. Keep scope small, working demo first.
- Developer is a beginner-to-intermediate. Explain in simple words, keep replies short.
- Challenge page: https://www.spaceappschallenge.org/2026/challenges/planet-x-and-spherex/ (could not be fetched by bot, text below is from the user's copy)

## The challenge (summary)
- Difficulty: Advanced. Subjects: Astrophysics, Planets and Moons, Software.
- NASA's SPHEREx mission (since 2025) maps the whole sky every 6 months in 102 near-infrared bands, with images of over a billion objects.
- Comets, asteroids, stars, brown dwarfs and new planets show up by shifting position between images (like Pluto's discovery, and Backyard Worlds citizen science).
- Goal: a PUBLIC-FACING WEB TOOL. User enters RA/Dec of a sky patch. The tool shows a series of images of that patch like a little video so moving objects are easy to spot.
- Test targets:
  - Barnard's Star
  - Epsilon Indi B (brown dwarf pair orbiting a star)
  - WISE 0855 (fast-moving brown dwarf): RA 08h55m10.831s, Dec -7d14m42.53s = RA 133.7951 deg, Dec -7.2451 deg
  - Variable stars RW Aurigae and R Draconis
- Optional ideas from the challenge:
  - Easy to update with new data releases
  - Combine the 6 detector arrays (D1 to D6) to improve signal-to-noise; generate spectra on the fly
  - Add or subtract images from different times
  - User-selectable field of view
  - Overlay Gaia or WISE data
  - Coordinates in the URL so it can be embedded
  - Show metadata such as contamination flags
  - Useful tools: astropy, Aladin (CDS)

## Agreed scope (must-haves)
1. Input box for RA/Dec plus one-click preset buttons for each test target.
2. Fetch SPHEREx image cutouts for that spot, sorted by observation date (oldest to newest).
3. Player: play/pause, time slider, date shown on each frame, looping.
4. Field-of-view choice (small = sharper, large = catches faster movers but slower to load).
5. URL parameters, e.g. `?ra=133.8&dec=-7.2` (and `&fov=`), so the page can be shared or embedded.

## Our unique feature: "Mover Spotter"
Most teams will just build the video player. Ours automatically detects objects that shift between frames, circles them, draws their path as a trail, and on click shows that object's brightness over time. Suggested approach: per-frame source detection (e.g. `photutils` DAOStarFinder or simple thresholding), match sources between frames, flag those whose position changes beyond noise or beyond the expected pointing/WCS error, then draw trails. Do it AFTER the basic player works.

## Stretch goals (only if time allows)
- Stack images per detector (D1 to D6) to improve signal-to-noise.
- Gaia or WISE overlay.
- On-the-fly spectrum plot.
- Show FLAGS (contamination) layer.

## Data source: NASA IRSA (IPAC Infrared Science Archive)
Official public SPHEREx archive. Findings from docs (verify when testing, details may change):

1. Find which images cover a position, with observation times, via TAP (pyvo):
   - Service: `https://irsa.ipac.caltech.edu/TAP`
   - Tables: `spherex.artifact` joined to `spherex.plane` on `planeid`
   - Example query pattern from IRSA tutorial:
     ```sql
     SELECT 'https://irsa.ipac.caltech.edu/' || a.uri || '?center={ra},{dec}d&size={size}' AS uri,
            p.time_bounds_lower
     FROM spherex.artifact a
     JOIN spherex.plane p ON a.planeid = p.planeid
     WHERE ... (position intersects, optional detector/bandpass filter)
     ORDER BY p.time_bounds_lower
     ```
   - The tutorial filters by bandpass such as `'SPHEREx-D2'`. Check the tutorial for the exact WHERE clause.
2. Download a cutout by appending `?center=RA,DEC&size=DEGREES` (size in degrees, e.g. 0.1) to the image URL.
   - Example: `curl -o cutout.fits "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr/level2/2025W19_2B/l2b-v11-2025-163/3/level2_2025W19_2B_0073_2D3_spx_l2b-v11-2025-163.fits?center=156.09328159,-41.64466331&size=0.1"`
   - An older form also exists: `https://irsa.ipac.caltech.edu/ibe/cutout?ra=..&dec=..&size=..&path=spherex/qr/level2/...fits`
3. Cutout output is a multi-extension FITS (MEF) with HDUs: IMAGE, FLAGS, VARIANCE, ZODI, PSF, WCS-WAVE. Use `hdul['IMAGE'].data` for the picture and `hdul['FLAGS']` for contamination info.
4. Other access routes: SIA2 (`https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_qr`), the SPHEREx Data Explorer web GUI, and astroquery/pyvo.
5. Releases are weekly "quick releases" (QR). Data was reprocessed with improved calibration in Oct 2025. Design the tool so new data is picked up automatically by querying TAP live (no hardcoded file lists).

Useful links:
- Cutout docs: https://irsa.ipac.caltech.edu/data/SPHEREx/docs/cutout_tool.html
- Cutout tutorial code: https://caltech-ipac.github.io/irsa-tutorials/spherex-cutouts
- PSF tutorial: https://caltech-ipac.github.io/irsa-tutorials/spherex-psf/
- Data access guide: https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access
- Explanatory Supplement: https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp_QR.pdf

## Known risks and open questions
- Cutouts are FITS, not images, so a Python backend must convert them to PNG frames (normalize, e.g. asinh or percentile stretch). Do NOT assume the browser can call IRSA directly (CORS unconfirmed).
- A note from a Nov 2025 IVOA meeting said IRSA was considering requiring login for downloads in 2026. Test anonymous access first. If blocked, tell the user.
- SPHEREx images each cover only part of a spectral band (the wavelength varies across a detector), so frames from different dates can look different in brightness. Consider choosing one detector per movie, or stacking per detector, to keep frames comparable.
- Frames may need to be aligned using each cutout's WCS (reproject with `astropy`/`reproject`) so that stars stay fixed and only movers shift. This matters for the mover detection.
- Star and brown dwarf coordinates: resolve names with `astropy.coordinates.SkyCoord.from_name(...)` (SIMBAD) rather than hardcoding. Epsilon Indi B is a companion of Epsilon Indi A. Proper motion is large for Barnard's Star, WISE 0855 and Epsilon Indi, which is what the demo should show.

## Suggested stack
- Backend: Python, FastAPI, `pyvo`, `astropy`, `numpy`, `Pillow`, optional `photutils`, `reproject`. Cache cutouts on disk.
- Frontend: plain HTML/JS or small React. No heavy framework needed. Canvas for the player and overlays (circles, trails), small chart for the brightness curve.
- Endpoints (suggested): `GET /api/frames?ra=&dec=&fov=&detector=` returns JSON list of `{date, png_url, flags_url}`. `GET /api/movers?...` returns detected movers with positions per frame.

## Order of work
1. Test script: get cutouts for WISE 0855 from IRSA and save as PNG frames in date order. (DECIDES EVERYTHING. If data cannot be fetched, stop and report.)
2. Backend API for frames.
3. Frontend: inputs, presets, player, slider, dates, FOV, URL params.
4. Mover Spotter (detection, circles, trails, brightness curve).
5. Test on all 5 targets, then polish and write a short README.
6. Stretch goals if time remains.

## Working style
- Short answers. Simple words. Get something visible working early, then add features.
- Ask before big changes. Keep the code small and readable.
