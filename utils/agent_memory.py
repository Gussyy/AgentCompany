"""
agent_memory.py — Long-term graph memory for each AgentCompany employee.

PRIMARY backend: FalkorDB (open-source Redis graph DB, runs locally via Docker).
  Start with:  docker-compose up -d   (from the project root)
  Browser UI:  http://localhost:3000

FALLBACK backend: SQLite (used automatically if FalkorDB is not running).

Graph schema:
  Nodes:  Industry, Product, PainPoint, Competitor, Pattern, Insight, Risk
  Edges:  HAS_PAIN_POINT, COMPETED_WITH, LED_TO_PRODUCT, SOLVED_BY,
          CAUSED_KILL, CAUSED_PASS, RELATES_TO, LEARNED_FROM

Usage (same API regardless of backend):
  mem = AgentMemoryGraph("ARIA")
  mem.add_node("Industry", "B2B logistics", {"run_count": 3})
  mem.add_edge("Industry", "B2B logistics", "HAS_PAIN_POINT", "PainPoint", "Manual tracking")
  context = mem.recall_for_industry("B2B logistics")
"""
from __future__ import annotations

import json, sqlite3, uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

MEMORY_DIR   = Path(__file__).parent.parent / "data" / "memory"
FALKORDB_HOST = "localhost"
FALKORDB_PORT = 6379


# ── Backend detection ─────────────────────────────────────────────────────────

def _try_falkordb(agent_name: str):
    """Try to connect to FalkorDB. Returns graph object or raises."""
    from falkordb import FalkorDB
    db = FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT)
    g  = db.select_graph(f"agent_{agent_name.replace('-','_')}")
    # Ping test
    g.query("RETURN 1")
    return db, g


# ══════════════════════════════════════════════════════════════════════════════
# FalkorDB backend
# ══════════════════════════════════════════════════════════════════════════════

class FalkorBackend:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self._db, self._g = _try_falkordb(agent_name)
        self._ensure_indexes()

    def _ensure_indexes(self):
        for label in ["Industry","Product","PainPoint","Competitor","Pattern","Risk"]:
            try:
                self._g.query(f"CREATE INDEX FOR (n:{label}) ON (n.label)")
            except Exception:
                pass

    def add_node(self, node_type: str, label: str, props: dict = None) -> str:
        props = props or {}
        now   = datetime.now().isoformat()
        # Check existing
        res = self._g.query(
            f"MATCH (n:{node_type} {{label: $lbl}}) RETURN n.id",
            {"lbl": label}
        )
        rows = res.result_set
        if rows:
            node_id = rows[0][0]
            # Update props
            set_clauses = ", ".join(f"n.{k} = ${k}" for k in props)
            if set_clauses:
                params = {"lbl": label, **props}
                self._g.query(
                    f"MATCH (n:{node_type} {{label: $lbl}}) SET {set_clauses}, n.updated_at = $ua",
                    {**params, "ua": now}
                )
            return node_id
        else:
            node_id = str(uuid.uuid4())[:8]
            prop_str = ", ".join(f"n.{k} = ${k}" for k in list({"id","label","created_at","updated_at"}) + list(props.keys()))
            self._g.query(
                f"CREATE (n:{node_type}) SET n.id = $id, n.label = $lbl, "
                f"n.created_at = $ca, n.updated_at = $ca"
                + (", " + ", ".join(f"n.{k} = ${k}" for k in props) if props else ""),
                {"id": node_id, "lbl": label, "ca": now, **props}
            )
            return node_id

    def add_edge(self, from_type, from_label, rel_type, to_type, to_label, props=None):
        props = props or {}
        now   = datetime.now().isoformat()
        self.add_node(from_type, from_label)
        self.add_node(to_type, to_label)
        # Check existing edge
        res = self._g.query(
            f"MATCH (a:{from_type} {{label:$fl}})-[r:{rel_type}]->(b:{to_type} {{label:$tl}}) "
            f"RETURN r.count",
            {"fl": from_label, "tl": to_label}
        )
        if res.result_set:
            count = (res.result_set[0][0] or 1) + 1
            self._g.query(
                f"MATCH (a:{from_type} {{label:$fl}})-[r:{rel_type}]->(b:{to_type} {{label:$tl}}) "
                f"SET r.count = $c",
                {"fl": from_label, "tl": to_label, "c": count}
            )
        else:
            count = 1
            prop_set = f", r.count = 1, r.created_at = $ca"
            if props:
                prop_set += ", " + ", ".join(f"r.{k} = ${k}" for k in props)
            self._g.query(
                f"MATCH (a:{from_type} {{label:$fl}}), (b:{to_type} {{label:$tl}}) "
                f"CREATE (a)-[r:{rel_type}]->(b) SET r.created_at = $ca, r.count = 1"
                + (", " + ", ".join(f"r.{k} = ${k}" for k in props) if props else ""),
                {"fl": from_label, "tl": to_label, "ca": now, **props}
            )

    def recall_for_industry(self, industry: str) -> str:
        lines = []
        try:
            # Industry node
            res = self._g.query(
                "MATCH (n:Industry {label: $lbl}) RETURN n",
                {"lbl": industry}
            )
            if not res.result_set:
                return ""
            n = res.result_set[0][0].properties
            lines.append(f"[{self.agent_name} LONG-TERM MEMORY — {industry}]")
            lines.append(f"• Runs: {n.get('run_count',0)} | Last: {n.get('last_run','?')} | Outcome: {n.get('last_outcome','?')}")

            # Pain points
            pp = self._g.query(
                "MATCH (i:Industry {label:$lbl})-[:HAS_PAIN_POINT]->(p:PainPoint) RETURN p ORDER BY p.severity DESC LIMIT 5",
                {"lbl": industry}
            )
            if pp.result_set:
                lines.append("• Known pain points:")
                for row in pp.result_set:
                    p = row[0].properties
                    lines.append(f"  - {p.get('label','?')} (sev:{p.get('severity','?')}, freq:{p.get('frequency','?')})")

            # Past products
            prods = self._g.query(
                "MATCH (i:Industry {label:$lbl})-[:LED_TO_PRODUCT]->(p:Product) RETURN p ORDER BY p.gate_score DESC LIMIT 3",
                {"lbl": industry}
            )
            if prods.result_set:
                lines.append("• Past products:")
                for row in prods.result_set:
                    p = row[0].properties
                    lines.append(f"  - {p.get('label','?')} → GATE:{p.get('gate_score','?')} ({p.get('status','?')})")

            # Competitors
            comps = self._g.query(
                "MATCH (i:Industry {label:$lbl})-[:COMPETED_WITH]->(c:Competitor) RETURN c LIMIT 4",
                {"lbl": industry}
            )
            if comps.result_set:
                lines.append("• Known competitors:")
                for row in comps.result_set:
                    c = row[0].properties
                    lines.append(f"  - {c.get('label','?')} (threat:{c.get('threat_level','?')})")

        except Exception as e:
            return f"[Memory read error: {e}]"
        return "\n".join(lines)

    def get_full_graph(self) -> dict:
        nodes, edges = [], []
        try:
            res = self._g.query("MATCH (n) RETURN n")
            for row in res.result_set:
                n = row[0]
                nodes.append({"id": n.properties.get("id",""), "type": list(n.labels)[0] if n.labels else "Unknown",
                               "label": n.properties.get("label",""), "props": dict(n.properties)})
            res2 = self._g.query("MATCH (a)-[r]->(b) RETURN a.label, type(r), b.label, r.count, a.id, b.id")
            for row in res2.result_set:
                edges.append({"from_label": row[0], "rel_type": row[1], "to_label": row[2],
                              "props": {"count": row[3]}, "from_id": row[4], "to_id": row[5]})
        except Exception:
            pass
        return {"agent": self.agent_name, "nodes": nodes, "edges": edges, "backend": "falkordb"}

    def stats(self) -> dict:
        try:
            nc = self._g.query("MATCH (n) RETURN count(n)").result_set[0][0]
            ec = self._g.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
            by_type_res = self._g.query("MATCH (n) RETURN labels(n)[0], count(n)")
            by_type = {row[0]: row[1] for row in by_type_res.result_set}
            return {"agent": self.agent_name, "nodes": nc, "edges": ec, "by_type": by_type, "backend": "falkordb"}
        except Exception:
            return {"agent": self.agent_name, "nodes": 0, "edges": 0, "by_type": {}, "backend": "falkordb"}

    def close(self): pass


# ══════════════════════════════════════════════════════════════════════════════
# SQLite fallback backend (same public API as FalkorBackend)
# ══════════════════════════════════════════════════════════════════════════════

class SQLiteBackend:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(MEMORY_DIR / f"{agent_name}.db"), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY, type TEXT, label TEXT,
                props TEXT DEFAULT '{}', created_at TEXT, updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY, from_id TEXT, to_id TEXT,
                rel_type TEXT, props TEXT DEFAULT '{}', created_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_nl ON nodes(type,label);
            CREATE INDEX IF NOT EXISTS idx_ef ON edges(from_id);
            CREATE INDEX IF NOT EXISTS idx_et ON edges(to_id);
        """); self._conn.commit()

    def add_node(self, node_type, label, props=None):
        props = props or {}; now = datetime.now().isoformat()
        cur = self._conn.cursor()
        cur.execute("SELECT id,props FROM nodes WHERE type=? AND label=?", (node_type, label))
        row = cur.fetchone()
        if row:
            existing = json.loads(row["props"]); existing.update(props)
            cur.execute("UPDATE nodes SET props=?,updated_at=? WHERE id=?", (json.dumps(existing), now, row["id"]))
            self._conn.commit(); return row["id"]
        nid = str(uuid.uuid4())[:8]
        cur.execute("INSERT INTO nodes VALUES (?,?,?,?,?,?)", (nid,node_type,label,json.dumps(props),now,now))
        self._conn.commit(); return nid

    def add_edge(self, from_type, from_label, rel_type, to_type, to_label, props=None):
        props = props or {}; now = datetime.now().isoformat()
        fid = self.add_node(from_type, from_label)
        tid = self.add_node(to_type, to_label)
        cur = self._conn.cursor()
        cur.execute("SELECT id,props FROM edges WHERE from_id=? AND to_id=? AND rel_type=?", (fid,tid,rel_type))
        row = cur.fetchone()
        if row:
            ep = json.loads(row["props"]); ep.update(props); ep["count"] = ep.get("count",1)+1
            cur.execute("UPDATE edges SET props=? WHERE id=?", (json.dumps(ep), row["id"]))
        else:
            props["count"] = 1
            cur.execute("INSERT INTO edges VALUES (?,?,?,?,?,?)", (str(uuid.uuid4())[:8],fid,tid,rel_type,json.dumps(props),now))
        self._conn.commit()

    def recall_for_industry(self, industry: str) -> str:
        ind = self._conn.execute("SELECT * FROM nodes WHERE type='Industry' AND label=?", (industry,)).fetchone()
        if not ind: return ""
        p = json.loads(ind["props"])
        lines = [f"[{self.agent_name} LONG-TERM MEMORY — {industry}]",
                 f"• Runs: {p.get('run_count',0)} | Last: {p.get('last_run','?')} | Outcome: {p.get('last_outcome','?')}"]
        # Pain points
        pps = self._conn.execute("""
            SELECT n.label, n.props FROM edges e JOIN nodes n ON e.to_id=n.id
            JOIN nodes i ON e.from_id=i.id
            WHERE i.label=? AND e.rel_type='HAS_PAIN_POINT' ORDER BY n.props DESC LIMIT 5
        """, (industry,)).fetchall()
        if pps:
            lines.append("• Known pain points:")
            for r in pps:
                pp = json.loads(r["props"])
                lines.append(f"  - {r['label']} (sev:{pp.get('severity','?')}, freq:{pp.get('frequency','?')})")
        # Products
        prods = self._conn.execute("""
            SELECT n.label, n.props FROM edges e JOIN nodes n ON e.to_id=n.id
            JOIN nodes i ON e.from_id=i.id
            WHERE i.label=? AND e.rel_type='LED_TO_PRODUCT' LIMIT 3
        """, (industry,)).fetchall()
        if prods:
            lines.append("• Past products:")
            for r in prods:
                pp = json.loads(r["props"])
                lines.append(f"  - {r['label']} → GATE:{pp.get('gate_score','?')} ({pp.get('status','?')})")
        # Competitors
        comps = self._conn.execute("""
            SELECT n.label, n.props FROM edges e JOIN nodes n ON e.to_id=n.id
            JOIN nodes i ON e.from_id=i.id
            WHERE i.label=? AND e.rel_type='COMPETED_WITH' LIMIT 4
        """, (industry,)).fetchall()
        if comps:
            lines.append("• Known competitors:")
            for r in comps:
                cp = json.loads(r["props"])
                lines.append(f"  - {r['label']} (threat:{cp.get('threat_level','?')})")
        return "\n".join(lines)

    def get_full_graph(self):
        nodes = [{**dict(r), "props": json.loads(r["props"])} for r in self._conn.execute("SELECT * FROM nodes ORDER BY updated_at DESC").fetchall()]
        edges = []
        for r in self._conn.execute("""
            SELECT e.*, nf.label as from_label, nf.type as from_type, nt.label as to_label, nt.type as to_type
            FROM edges e JOIN nodes nf ON e.from_id=nf.id JOIN nodes nt ON e.to_id=nt.id
        """).fetchall():
            edges.append({**dict(r), "props": json.loads(r["props"])})
        return {"agent": self.agent_name, "nodes": nodes, "edges": edges, "backend": "sqlite"}

    def stats(self):
        nc = self._conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        ec = self._conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        by_type = {r[0]: r[1] for r in self._conn.execute("SELECT type, COUNT(*) FROM nodes GROUP BY type").fetchall()}
        return {"agent": self.agent_name, "nodes": nc, "edges": ec, "by_type": by_type, "backend": "sqlite"}

    def close(self): self._conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# Unified AgentMemoryGraph — picks FalkorDB or SQLite automatically
# ══════════════════════════════════════════════════════════════════════════════

class AgentMemoryGraph:
    """
    Public interface — automatically uses FalkorDB if running, else SQLite.
    The calling code never needs to know which backend is active.
    """
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self._backend_name = "unknown"
        try:
            self._backend = FalkorBackend(agent_name)
            self._backend_name = "falkordb"
        except Exception:
            self._backend = SQLiteBackend(agent_name)
            self._backend_name = "sqlite"

    @property
    def backend(self) -> str:
        return self._backend_name

    def add_node(self, node_type: str, label: str, props: dict = None) -> str:
        return self._backend.add_node(node_type, label, props)

    def add_edge(self, from_type, from_label, rel_type, to_type, to_label, props=None):
        return self._backend.add_edge(from_type, from_label, rel_type, to_type, to_label, props)

    def recall_for_industry(self, industry: str) -> str:
        return self._backend.recall_for_industry(industry)

    def get_full_graph(self) -> dict:
        return self._backend.get_full_graph()

    def stats(self) -> dict:
        s = self._backend.stats()
        s["backend"] = self._backend_name
        return s

    def remember_run(self, industry: str, result: dict):
        """Store learnings from a completed run into the knowledge graph."""
        def _s(obj):
            if obj is None: return {}
            if isinstance(obj, dict): return obj
            try: return obj.model_dump()
            except: return {}
        status  = result.get("status", "unknown")
        passed  = status == "complete"
        pd = _s(result.get("product_design"))
        product = pd.get("name", "") or pd.get("product_name", "")
        gate_scores = result.get("gate_scores") or {}

        # Industry node
        existing = self._backend.stats()  # just to check connection
        run_count = 1
        try:
            summary = self.recall_for_industry(industry)
            import re
            m = re.search(r"Runs: (\d+)", summary)
            if m: run_count = int(m.group(1)) + 1
        except Exception:
            pass

        self.add_node("Industry", industry, {
            "run_count": run_count,
            "last_run": datetime.now().strftime("%Y-%m-%d"),
            "last_outcome": "pass" if passed else "kill",
        })

        # Product
        if product:
            composite = next(
                (v.get("composite_score") for v in gate_scores.values() if isinstance(v, dict) and v.get("composite_score")),
                None
            )
            self.add_node("Product", product, {
                "industry": industry, "gate_score": composite,
                "status": "pass" if passed else "kill",
                "date": datetime.now().strftime("%Y-%m-%d"),
            })
            self.add_edge("Industry", industry, "LED_TO_PRODUCT", "Product", product,
                          {"outcome": "pass" if passed else "kill"})

        # Pain points from ARIA
        friction = _s(result.get("friction_report"))
        fp_list = friction.get("friction_points") or []
        for fp in fp_list:
            title = fp.get("title") if isinstance(fp, dict) else getattr(fp, "title", "")
            if not title: continue
            self.add_node("PainPoint", title, {
                "industry": industry,
                "severity":  fp.get("severity",0)  if isinstance(fp,dict) else getattr(fp,"severity",0),
                "frequency": fp.get("frequency",0) if isinstance(fp,dict) else getattr(fp,"frequency",0),
            })
            self.add_edge("Industry", industry, "HAS_PAIN_POINT", "PainPoint", title)

        # Competitors from SENTRY
        sentry = _s(result.get("competitive_intel"))
        for comp in (sentry.get("competitors") or []):
            name = comp.get("name", "")
            if not name: continue
            self.add_node("Competitor", name, {
                "threat_level": comp.get("threat_level", "green"),
                "positioning":  comp.get("positioning", ""),
            })
            self.add_edge("Industry", industry, "COMPETED_WITH", "Competitor", name)

        # GATE pattern
        for stage, scores in gate_scores.items():
            if not isinstance(scores, dict): continue
            composite = scores.get("composite_score")
            if composite is None: continue
            label = f"{industry}:{stage}"
            self.add_node("Pattern", label, {
                "composite": composite, "outcome": "pass" if passed else "kill",
                "market_opportunity": scores.get("market_opportunity"),
                "competitive_edge":   scores.get("competitive_edge"),
                "financial_viability":scores.get("financial_viability"),
                "execution_risk":     scores.get("execution_risk"),
            })
            self.add_edge("Industry", industry,
                          "CAUSED_PASS" if passed else "CAUSED_KILL",
                          "Pattern", label)

    def close(self):
        self._backend.close()
