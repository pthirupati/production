"""PeopleSoft PIA V2 facades — Query Manager, PeopleCode, GL journals, AP/AR, payroll."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_v2() -> dict[str, Any]:
    return {
        "queries": [
            {
                "id": "QRY_EMP_ACTIVE",
                "name": "FIXITLAB_ACTIVE_EMPLOYEES",
                "owner": "PS",
                "public": True,
                "records": ["JOB", "PERSONAL_DATA"],
                "fields": ["EMPLID", "NAME", "DEPTID", "JOBCODE", "ANNUAL_RT"],
                "criteria": "JOB.EFF_STATUS = 'A'",
                "last_run": None,
                "row_count": 0,
            },
        ],
        "peoplecode": [
            {
                "id": "pc-salary",
                "object": "JOB.ANNUAL_RT.FieldChange",
                "language": "PeopleCode",
                "body": (
                    "Function SalaryCheck()\n"
                    "   Local number &maxSal;\n"
                    "   &maxSal = GetRecord(Record.JOB).GRADE_SAL_MAX.Value;\n"
                    "   If GetRecord(Record.JOB).ANNUAL_RT.Value > &maxSal Then\n"
                    "      Error \"Salary exceeds grade maximum\";\n"
                    "   End-If;\n"
                    "End-Function;\n"
                ),
                "validated": True,
            },
        ],
        "journals": [
            {
                "id": "JRNL-1001",
                "business_unit": "CORP01",
                "journal_date": "2024-06-25",
                "ledger": "ACTUALS",
                "status": "Posted",
                "balanced": True,
                "lines": [
                    {"account": "6100", "dept": "MKTG", "debit": 5000, "credit": 0, "descr": "Professional services"},
                    {"account": "2000", "dept": "CORP", "debit": 0, "credit": 5000, "descr": "Accrued liabilities"},
                ],
            },
        ],
        "vouchers": [
            {
                "id": "VCHR-2201",
                "vendor": "ACME CONSULTING",
                "invoice": "INV-8891",
                "gross": 12500.00,
                "status": "Approved",
                "due_date": "2024-07-15",
            },
        ],
        "ar_invoices": [
            {
                "id": "AR-4401",
                "customer": "CONTOSO LTD",
                "amount": 8200.00,
                "status": "Open",
                "aging_bucket": "1-30",
            },
        ],
        "pay_runs": [
            {
                "id": "PAY-2024-13",
                "pay_group": "USA",
                "period_end": "2024-06-21",
                "status": "Confirmed",
                "employees": 142,
                "gross": 892450.00,
                "net": 612330.00,
            },
        ],
        "trial_balance": [
            {"account": "1000", "descr": "Cash", "debit": 250000, "credit": 0},
            {"account": "2000", "descr": "Accrued liabilities", "debit": 0, "credit": 45000},
            {"account": "4000", "descr": "Revenue", "debit": 0, "credit": 520000},
            {"account": "6100", "descr": "Professional services", "debit": 85000, "credit": 0},
        ],
    }


def ensure_v2(world: dict) -> None:
    v2 = world.setdefault("v2", {})
    for key, value in seed_v2().items():
        if key not in v2 or v2.get(key) is None:
            v2[key] = value


def apply_v2_action(world: dict, action: str, payload: dict | None = None) -> dict | None:
    payload = payload or {}
    ensure_v2(world)
    v2 = world["v2"]

    if action == "create_query":
        name = (payload.get("name") or f"QRY_{len(v2.get('queries') or []) + 1}").strip().upper()
        row = {
            "id": name,
            "name": name,
            "owner": payload.get("owner") or world.get("session", {}).get("oprid") or "PS",
            "public": bool(payload.get("public", True)),
            "records": payload.get("records") or ["JOB"],
            "fields": payload.get("fields") or ["EMPLID", "NAME"],
            "criteria": payload.get("criteria") or "",
            "last_run": None,
            "row_count": 0,
        }
        v2.setdefault("queries", []).append(row)
        return {"ok": True, "message": f"Query {name} saved", "query": row}

    if action == "run_query":
        qid = payload.get("query_id") or payload.get("name") or ""
        q = next((x for x in v2.get("queries") or [] if x.get("id") == qid or x.get("name") == qid), None)
        if not q and (v2.get("queries") or []):
            q = v2["queries"][0]
        if not q:
            return {"ok": False, "error": "Query not found"}
        # Deterministic fake result set sized by field count.
        rows = [
            {"EMPLID": "1001", "NAME": "Ada Lovelace", "DEPTID": "IT", "JOBCODE": "DEV", "ANNUAL_RT": 145000},
            {"EMPLID": "1002", "NAME": "Grace Hopper", "DEPTID": "IT", "JOBCODE": "ARCH", "ANNUAL_RT": 168000},
            {"EMPLID": "1003", "NAME": "Alan Turing", "DEPTID": "R&D", "JOBCODE": "SCI", "ANNUAL_RT": 152000},
        ]
        q["last_run"] = _now()
        q["row_count"] = len(rows)
        q["preview"] = rows
        return {"ok": True, "message": f"Query returned {len(rows)} rows", "query": q, "rows": rows}

    if action == "save_peoplecode":
        obj = (payload.get("object") or "JOB.ANNUAL_RT.FieldChange").strip()
        body = payload.get("body") or ""
        if "Error" not in body and "End-Function" not in body and body:
            # Soft validate — still save but flag.
            validated = "Function" in body
        else:
            validated = True
        row = {
            "id": f"pc-{len(v2.get('peoplecode') or []) + 1}",
            "object": obj,
            "language": "PeopleCode",
            "body": body,
            "validated": validated,
            "saved_at": _now(),
        }
        pcs = v2.setdefault("peoplecode", [])
        existing = next((p for p in pcs if p.get("object") == obj), None)
        if existing:
            existing.update(row)
            row = existing
        else:
            pcs.append(row)
        return {"ok": True, "message": f"PeopleCode saved for {obj}", "peoplecode": row}

    if action == "create_journal":
        lines = payload.get("lines") or [
            {"account": "6100", "dept": "MKTG", "debit": 1000, "credit": 0, "descr": "Expense"},
            {"account": "2000", "dept": "CORP", "debit": 0, "credit": 1000, "descr": "Accrual"},
        ]
        debit = sum(float(l.get("debit") or 0) for l in lines)
        credit = sum(float(l.get("credit") or 0) for l in lines)
        balanced = abs(debit - credit) < 0.01
        if not balanced and not payload.get("allow_unbalanced"):
            return {"ok": False, "error": f"Journal not balanced (debit={debit}, credit={credit})"}
        row = {
            "id": f"JRNL-{1000 + len(v2.get('journals') or []) + 1}",
            "business_unit": payload.get("business_unit") or "CORP01",
            "journal_date": payload.get("journal_date") or _now()[:10],
            "ledger": payload.get("ledger") or "ACTUALS",
            "status": "Posted" if payload.get("post") else "Saved",
            "balanced": balanced,
            "lines": lines,
        }
        v2.setdefault("journals", []).insert(0, row)
        return {"ok": True, "message": f"Journal {row['id']} {'posted' if row['status'] == 'Posted' else 'saved'}", "journal": row}

    if action == "create_voucher":
        row = {
            "id": f"VCHR-{2200 + len(v2.get('vouchers') or []) + 1}",
            "vendor": payload.get("vendor") or "VENDOR INC",
            "invoice": payload.get("invoice") or f"INV-{len(v2.get('vouchers') or []) + 1}",
            "gross": float(payload.get("gross") or 1000),
            "status": payload.get("status") or "Entered",
            "due_date": payload.get("due_date") or _now()[:10],
        }
        v2.setdefault("vouchers", []).insert(0, row)
        return {"ok": True, "message": f"Voucher {row['id']} created", "voucher": row}

    if action == "create_ar_invoice":
        row = {
            "id": f"AR-{4400 + len(v2.get('ar_invoices') or []) + 1}",
            "customer": payload.get("customer") or "CUSTOMER CO",
            "amount": float(payload.get("amount") or 500),
            "status": "Open",
            "aging_bucket": payload.get("aging_bucket") or "Current",
        }
        v2.setdefault("ar_invoices", []).insert(0, row)
        return {"ok": True, "message": f"Invoice {row['id']} created", "invoice": row}

    if action == "run_payroll":
        row = {
            "id": f"PAY-{_now()[:7].replace('-', '')}-{len(v2.get('pay_runs') or []) + 1}",
            "pay_group": payload.get("pay_group") or "USA",
            "period_end": payload.get("period_end") or _now()[:10],
            "status": "Calculated",
            "employees": int(payload.get("employees") or 142),
            "gross": float(payload.get("gross") or 890000),
            "net": float(payload.get("net") or 610000),
        }
        if payload.get("confirm"):
            row["status"] = "Confirmed"
        v2.setdefault("pay_runs", []).insert(0, row)
        return {"ok": True, "message": f"Pay run {row['id']} {row['status'].lower()}", "pay_run": row}

    return None
