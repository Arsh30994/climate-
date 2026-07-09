"""
Seeds two pilot regions so the app has something to look at immediately
after clone, without waiting on real IMD/MOSDAC access. Run standalone:

    python -m app.seed_data

or it runs automatically on first `run.py` boot if the DB is empty.
"""
from app.database import SessionLocal, init_db
from app.models import Region

DEMO_REGIONS = [
    dict(
        name="Marathwada, Maharashtra",
        description="Drought-prone semi-arid pilot region -- rainfall variability use case.",
        lat_min=18.2, lat_max=19.9, lon_min=75.3, lon_max=77.5,
        grid_resolution_deg=0.25,
    ),
    dict(
        name="Sangrur-Barnala, Punjab",
        description="Rabi-cropping belt pilot region -- reused from the crop-monitoring project for continuity.",
        lat_min=29.9, lat_max=30.4, lon_min=75.3, lon_max=75.9,
        grid_resolution_deg=0.25,
    ),
]


def seed():
    init_db()
    db = SessionLocal()
    try:
        created = 0
        for r in DEMO_REGIONS:
            if not db.query(Region).filter(Region.name == r["name"]).first():
                db.add(Region(**r))
                created += 1
        db.commit()
        print(f"Seeded {created} region(s). Total regions: {db.query(Region).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
