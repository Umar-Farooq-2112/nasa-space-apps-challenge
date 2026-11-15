"""Look at what IRSA's SPHEREx tables contain (column names + a sample query)."""
import pyvo

tap = pyvo.dal.TAPService("https://irsa.ipac.caltech.edu/TAP")
for t in ("spherex.artifact", "spherex.plane"):
    print("==", t)
    r = tap.run_sync(f"SELECT TOP 1 * FROM {t}")
    print(r.to_table().colnames)
