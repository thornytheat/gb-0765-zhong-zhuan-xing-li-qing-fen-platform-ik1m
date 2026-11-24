from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from app.errors import DeskError
from app.manifest import canonical


class Archive:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, inputs TEXT NOT NULL, result TEXT NOT NULL)')
            db.execute('''CREATE TABLE IF NOT EXISTS handovers (
                run_id TEXT NOT NULL, leg TEXT NOT NULL, receiver TEXT NOT NULL, receiver_kind TEXT NOT NULL,
                tags TEXT NOT NULL, bags INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'issued',
                recalled_at TEXT, PRIMARY KEY (run_id, leg))''')

    def connect(self):
        return sqlite3.connect(self.path, timeout=15)

    def commit(self, key, files, result):
        with closing(self.connect()) as db, db:
            cursor = db.execute('INSERT OR IGNORE INTO runs VALUES (?, ?, ?)', (key, canonical(files), canonical(result)))
            stored = db.execute('SELECT result FROM runs WHERE id=?', (key,)).fetchone()[0]
        return json.loads(stored), cursor.rowcount == 0

    def issue(self, run_id, orders):
        created = 0
        with closing(self.connect()) as db, db:
            for order in orders:
                cursor = db.execute(
                    'INSERT OR IGNORE INTO handovers (run_id, leg, receiver, receiver_kind, tags, bags) VALUES (?, ?, ?, ?, ?, ?)',
                    (run_id, order['leg'], order['receiver'], order['receiver_kind'], canonical(order['tags']), order['count']))
                created += cursor.rowcount
        return created

    def handovers(self, run_id):
        with closing(self.connect()) as db:
            rows = db.execute(
                'SELECT run_id, leg, receiver, receiver_kind, tags, bags, status, recalled_at FROM handovers WHERE run_id=? ORDER BY leg',
                (run_id,)).fetchall()
        return [dict(run=row[0], leg=row[1], receiver=row[2], receiver_kind=row[3], tags=json.loads(row[4]),
                     count=row[5], status=row[6], recalled_at=row[7]) for row in rows]

    def recall(self, run_id):
        stamp = datetime.now(timezone.utc).isoformat()
        with closing(self.connect()) as db, db:
            cursor = db.execute(
                "UPDATE handovers SET status='recalled', recalled_at=? WHERE run_id=? AND status='issued'",
                (stamp, run_id))
        return cursor.rowcount

    def get(self, key):
        with closing(self.connect()) as db:
            row = db.execute('SELECT inputs, result FROM runs WHERE id=?', (key,)).fetchone()
        if row is None:
            raise DeskError('NO_RUN', '归档不存在', 404)
        return json.loads(row[0]), json.loads(row[1])

    def list(self):
        with closing(self.connect()) as db:
            rows = db.execute('SELECT result FROM runs ORDER BY rowid DESC').fetchall()
        return [json.loads(row[0])['manifest'] for row in rows]
