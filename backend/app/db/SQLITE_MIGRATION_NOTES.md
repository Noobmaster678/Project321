## SQLite migration notes (no Alembic)

This project currently does not use Alembic migrations. If you already have an existing
SQLite database file and you update models, you may need to apply manual `ALTER TABLE`
statements.

### Add Individual reference detections (left/right)

Add two nullable columns to `individuals` to store the ecologist-selected reference
detections used for side-by-side comparisons.

Run these statements against your SQLite DB:

```sql
ALTER TABLE individuals ADD COLUMN ref_left_detection_id INTEGER;
ALTER TABLE individuals ADD COLUMN ref_right_detection_id INTEGER;
```

Notes:

- SQLite cannot add foreign key constraints via `ALTER TABLE` in-place; the app will
  still enforce validity in the API layer.
