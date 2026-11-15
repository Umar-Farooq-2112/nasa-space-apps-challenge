import React from "react";

const ext = (href, text) => <a href={href} target="_blank" rel="noreferrer">{text}</a>;

export default function Guide({ onBack }) {
  return (
    <div className="guide">
      <p><button className="link" onClick={onBack}>&larr; Back to the viewer</button></p>
      <h1 style={{ fontSize: "1.4rem" }}>Where do I get images? (no code needed)</h1>
      <p className="muted">
        Mover Spotter needs <b>many images of the same patch of sky taken on different dates</b>, as FITS files. Each file must
        carry sky coordinates and a date in its header, which nearly every telescope archive provides.
      </p>

      <div className="card">
        <h2>Step 0: find your target's coordinates</h2>
        <ol>
          <li>Search for the object's name in {ext("https://simbad.cds.unistra.fr/simbad/", "SIMBAD")} or {ext("https://ned.ipac.caltech.edu/", "NED")}.</li>
          <li>Copy its <b>RA and Dec in decimal degrees</b> (ICRS / J2000), for example <code>123.4567 -12.3456</code>. You can paste both numbers at once into the RA box of the viewer.</li>
          <li><b>Fast-moving stars:</b> catalogue positions are for the year 2000. A star moving several arcseconds per year has drifted far by the 2010s-2020s. The default 200-pixel window is wide enough for most targets; for very fast stars shift the position by the proper motion listed on the same SIMBAD page, or make the window bigger.</li>
        </ol>
      </div>

      <div className="card">
        <h2>Source A: WISE / NEOWISE, one image per ~6 months from 2010 <span className="tag">tested</span></h2>
        <p>The "time-resolved coadds" behind the public WiseView tool, hosted at NERSC. A plain web directory, no login. About 18 epochs per position.</p>
        <ol>
          <li><b>Find the tile name.</b> Open {ext("https://unwise.me/imgsearch/", "unwise.me/imgsearch")}, enter your RA/Dec and get a cutout. The downloaded archive holds file names like <code>unwise-<b>1342m076</b>-w2-img-m.fits</code>. The bold part (4 digits, <code>p</code> or <code>m</code>, 3 digits) is the <b>tile name</b>. (This example tile contains the brown dwarf WISE 0855.)</li>
          <li><b>Open the epoch folders.</b> Go to {ext("https://portal.nersc.gov/project/cosmo/temp/ameisner/neo8/", "portal.nersc.gov/project/cosmo/temp/ameisner/neo8/")}. Folders <code>e000/</code>, <code>e001/</code>, ... are the time epochs.</li>
          <li><b>For each epoch</b> (e000 up to about e020) open <code>eNNN/&lt;first 3 digits of tile&gt;/&lt;tile&gt;/</code>, for example <code>e000/134/1342m076/</code>, and download <code>unwise-&lt;tile&gt;-w2-img-m.fits</code> (about 17 MB). <code>w2</code> is the 4.6 &micro;m band, best for cold objects; <code>w1</code> is 3.4 &micro;m. Pick one band. Epoch folders without your tile show "Not found": skip them.</li>
          <li><b>Upload</b> them all in the viewer. The files are huge (2048&times;2048 pixels), so enter the RA/Dec from step 0 in <b>Sky position</b>: the viewer crops around it. Dates come from the file headers.</li>
        </ol>
        <p className="muted small">The browser will add (1), (2) to repeated file names. That is fine: frames are ordered by the date in each header, not by file name.</p>
      </div>

      <div className="card">
        <h2>Source B: SPHEREx (NASA, 2025 onward) <span className="tag">from IRSA docs, not tested</span></h2>
        <p>SPHEREx is the mission this challenge is about. Its images come from the NASA/IPAC Infrared Science Archive (IRSA). <b>When this app was built IRSA's search service was down</b> (the Data Explorer said "TAP service does not appear to exist or is not accessible"), so these steps follow IRSA's documentation and are untested.</p>
        <ol>
          <li>Open the {ext("https://irsa.ipac.caltech.edu/applications/spherex", "SPHEREx Data Explorer")}, tab <b>Spectral Image Search</b>.</li>
          <li>Enter your RA/Dec (or name) and a small radius such as 0.05&deg;, then <b>Search</b>. You get one row per image, with its date.</li>
          <li>Download <b>cutouts</b> (small crops) instead of full images, see the {ext("https://irsa.ipac.caltech.edu/data/SPHEREx/docs/cutout_tool.html", "cutout tool documentation")}. About 0.1&deg; is enough. The viewer reads the <code>IMAGE</code> extension.</li>
          <li>Upload them. The viewer groups by detector (D1 to D6). <b>Use one detector at a time</b>: each sees a different wavelength.</li>
        </ol>
        <p className="muted small">You need at least <b>5 images in one band</b>. SPHEREx revisits the sky about every 6 months, so new dates arrive over time.</p>
      </div>

      <div className="card">
        <h2>Other sources</h2>
        <p>Any FITS image with <b>sky coordinates (WCS)</b> and a <b>date</b> in the header works. Upload several images of the same field and Mover Spotter does the rest.</p>
      </div>

      <div className="card">
        <h2>Using the viewer</h2>
        <ol>
          <li>Press <b>New</b>, name the dataset, <b>Create</b>.</li>
          <li>Drag your FITS files into the dashed box. Each file is reported OK or skipped with the reason.</li>
          <li>Set <b>Sky position</b> if your images are big. You can change it or <b>Clear</b> it at any time: nothing is re-uploaded and the original files are never touched.</li>
          <li>Pick the <b>band</b> and the <b>picture</b>. Everything updates by itself.</li>
        </ol>
        <table>
          <thead><tr><th>Message</th><th>What it means / what to do</th></tr></thead>
          <tbody>
            <tr><td>needs RA/Dec</td><td>The image is big and no position is set. Enter RA/Dec under Sky position.</td></tr>
            <tr><td>outside position</td><td>This image does not cover the position you set. Check the coordinates, or that you downloaded the right tile.</td></tr>
            <tr><td>no sky coordinates (WCS)</td><td>The file has no sky position, so positions cannot be tracked. Download the calibrated version.</td></tr>
            <tr><td>no observation date in the header</td><td>The file has none of the usual date keywords. Use another product from the archive.</td></tr>
            <tr><td>Need at least 5 frames in one band</td><td>Upload more dates, or check that the files landed in the same band.</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
