# Charon - project submission text

Copy each section into the matching field of the Space Apps project form.

## Project name

Charon

## High-level summary

In 1978 astronomers found Charon, Pluto's largest moon, by noticing one tiny bump that moved from photo to photo.
Charon, our app, does the same with NASA's SPHEREx space telescope, for anyone.
Pick a star, search a name, type coordinates or explore a random spot, and you watch a year of real SPHEREx infrared photos of that patch as a smooth, aligned flip-book.
The app then finds what moves on its own: it circles each mover, draws its path, measures its speed and direction with error bars, and checks the result against the Gaia catalog.
Because SPHEREx sees a slightly different color in every photo, a year of photos also gives each mover a spectrum, which shows whether it is a cold brown dwarf.
On real data it found all six fast-moving test objects (for example Epsilon Indi B: 4.35 ± 0.24 arcseconds per year, 7% from Gaia, direction within 5 degrees), with no false movers on the variable stars.
SPHEREx images a billion objects and no one person can check them all; Charon turns that data into something anyone can watch and help search, including for the next Planet X.

## Project details

**What it does**

- Shows any spot in the sky as a time-lapse of NASA SPHEREx photos, oldest to newest, aligned north-up so still stars stay put and movers visibly shift.
- Three ways to look: the real photos; "Changes only" (each photo minus the average sky, so still stars vanish); and "Deep view" (all photos stacked, about 3.5x less noise, so faint objects appear).
- Finds moving objects automatically and reports speed, direction, distance moved, track error and confidence, in plain words for the public (for example "like a coin seen from 1.1 km away sliding its own width in a year").
- Checks each find against the Gaia catalog (via SIMBAD) and shows how well they agree.
- Plots each mover's brightness over time and its spectrum.
- Covers all six SPHEREx detectors (0.75 to 5.0 micrometres); cold brown dwarfs glow at the long end.
- Search by star name (corrected for proper motion to 2026) or coordinates; "Explore a random spot" sends you somewhere nobody may have looked closely.
- Shareable and embeddable links (coordinates, zoom, detector and mode in the URL), raw FITS download of every photo, and CSV export of every measured position for scientists and citizen scientists.
- Always current: it uses NASA's newest SPHEREx release (currently up to 5 October 2026) and shows how fresh the data is.

**How it works**

- NASA's SPHEREx search service was down during the hackathon, so we built our own index of every SPHEREx image (about 270,000 per detector) from IRSA's public copy on AWS, by reading just the pointing information from each image's header.
  A search over the whole sky takes half a second, and re-running the index picks up each new weekly release.
- For a chosen spot, it cuts out a small square from up to 20 photos spread over the full time range using IRSA's cutout service, and keeps them so the next visit is instant.
- Each photo is resampled onto a common north-up grid using its own sky coordinates (WCS); bad pixels are filled from their neighbours using the SPHEREx quality flags.
- The tracker finds sources in every photo, removes small pointing shifts using the stars that stay still, links sources into straight-line tracks over time, and keeps only tracks that really move, with a fitted speed, direction and error.
- Brightness is measured with aperture photometry; the wavelength of each measurement comes from the SPHEREx spectral map (WCS-WAVE), which gives the spectrum.

**Validation on real SPHEREx data (20 photos over about a year)**

| Target | Found | Gaia catalog |
| --- | --- | --- |
| Barnard's Star | 8.7"/yr toward 351° | 10.4"/yr toward 356° |
| Epsilon Indi B | 4.35 ± 0.24"/yr toward 127° | 4.68"/yr toward 122° |
| Kapteyn's Star | 9.1"/yr toward 131° | 8.6"/yr toward 131° |
| Groombridge 1830 | 5.7"/yr toward 157° | 7.1"/yr toward 146° |
| Wolf 359 (fetched live, never cached) | 5.3"/yr toward 244° | 4.7"/yr toward 235° |
| Luhman 16 | 3.1"/yr toward 271° | 2.8"/yr toward 277° |
| RW Aurigae, R Draconis (variable stars) | no movers, correct | about 0.02"/yr |

The spectrum of Epsilon Indi B shows the water and methane dip near 1.8 to 1.95 micrometres that marks a cold brown dwarf.

**Benefits**

- Opens a brand-new NASA mission's data to anyone, with no astronomy knowledge or software needed.
- Scales the search: the computer checks every patch and people only review the circled candidates, the same model as the Backyard Worlds citizen-science project.
- Gives trustworthy results: every find comes with error bars, a confidence level and a catalog comparison.

**Tools**

Python, FastAPI, Astropy, NumPy, SciPy, Pillow, SQLite, and plain HTML, CSS and JavaScript (no build step).

**Limits and next steps**

- Very faint movers such as WISE 0855 are visible in the movie but too faint for the tracker in single photos; tracking on stacked photos (shift-and-stack) is the next step.
- Very crowded Milky Way fields (for example Proxima Centauri) confuse the tracker.
- Brightness values mix wavelengths, so they are indicative rather than calibrated.
- Next: combine all six detectors, overlay Gaia and WISE positions, and let users flag candidates for follow-up.

## Use of artificial intelligence

We used Claude Code (Anthropic) as an AI coding assistant to help write and test the code, and Microsoft Edge neural text-to-speech for the demo video's voice-over.
All data, images and scientific results come from NASA SPHEREx and the Gaia catalog; no AI-generated images or data are used in the app.

## NASA data

- SPHEREx Level 2 spectral images (Quick Release 3 and Data Release 1) - NASA/IPAC Infrared Science Archive (IRSA): https://irsa.ipac.caltech.edu/Missions/spherex.html
- SPHEREx public data on AWS (s3://nasa-irsa-spherex): https://nasa-irsa-spherex.s3.amazonaws.com
- IRSA SPHEREx cutout service: https://irsa.ipac.caltech.edu/data/SPHEREx/docs/cutout_tool.html

## Space agency partner data

- ESA Gaia (proper motions, via SIMBAD) and the CDS Sesame name resolver: https://cds.unistra.fr/cgi-bin/Sesame

## References

- SPHEREx Explanatory Supplement: https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp_QR.pdf
- IRSA SPHEREx tutorials: https://caltech-ipac.github.io/irsa-tutorials/
- Astropy, NumPy, SciPy, Pillow, FastAPI, Uvicorn (open-source Python libraries)
- Instrument Sans font (Google Fonts, SIL Open Font License)
- Backyard Worlds: Planet 9 (inspiration for the citizen-science approach): https://backyardworlds.org
