#!/usr/bin/env python3
"""
Verify snowflake_pricing_master.json against CreditConsumptionTable.pdf (effective May 12, 2026).

Ground-truth values below were extracted by visual inspection of the 21-page PDF.
Each check is labeled with the PDF table it comes from.

Exit code: 0 if all checks pass, 1 if discrepancies found.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = REPO_ROOT / "assets" / "snowflake_pricing_master.json"

errors = []
warnings = []


def fail(table, desc, expected, actual):
    errors.append(f"[{table}] {desc}: expected {expected!r}, got {actual!r}")


def warn(table, desc, note):
    warnings.append(f"[{table}] {desc}: {note}")


def check_eq(table, desc, expected, actual):
    if actual != expected:
        fail(table, desc, expected, actual)


def check_approx(table, desc, expected, actual, tol=0.001):
    if actual is None:
        fail(table, desc, expected, None)
        return
    if abs(actual - expected) > tol:
        fail(table, desc, expected, actual)


def find_one(collection, **kwargs):
    """Return first dict in collection matching all kwargs, or None."""
    for item in collection:
        if all(item.get(k) == v for k, v in kwargs.items()):
            return item
    return None


with open(JSON_PATH) as f:
    D = json.load(f)


# ---------------------------------------------------------------------------
# Table 1(a) – Standard Warehouse
# ---------------------------------------------------------------------------
T = "Table 1(a)"
std = {r["size"]: r["credits_per_hour"] for r in D["warehouses"]["standard"]["data"]}
for size, expected in [("XS", 1), ("S", 2), ("M", 4), ("L", 8), ("XL", 16),
                        ("2XL", 32), ("3XL", 64), ("4XL", 128), ("5XL", 256), ("6XL", 512)]:
    check_eq(T, f"size={size}", expected, std.get(size))


# ---------------------------------------------------------------------------
# Table 1(b) – Gen 2 Warehouse
# ---------------------------------------------------------------------------
T = "Table 1(b)"
gen2 = {r["cloud"]: r for r in D["warehouses"]["gen2"]["data"]}
for cloud, xs, s, m, l, xl, xxl, xxxl, xxxxl in [
    ("AWS",   1.35, 2.7, 5.4, 10.8, 21.6, 43.2, 86.4, 172.8),
    ("Azure", 1.25, 2.5, 5.0, 10.0, 20.0, 40.0, 80.0, 160.0),
    ("GCP",   1.35, 2.7, 5.4, 10.8, 21.6, 43.2, 86.4, 172.8),
]:
    r = gen2.get(cloud, {})
    for size, exp in [("XS", xs), ("S", s), ("M", m), ("L", l), ("XL", xl),
                      ("2XL", xxl), ("3XL", xxxl), ("4XL", xxxxl)]:
        check_approx(T, f"cloud={cloud} size={size}", exp, r.get(size))


# ---------------------------------------------------------------------------
# Table 1(c) – Snowpark Optimized Warehouses
# ---------------------------------------------------------------------------
T = "Table 1(c)"
spo = {r["constraint"]: r for r in D["snowpark_optimized"]["data"]}

# MEMORY_1X
check_approx(T, "MEMORY_1X XS", 1.0,   spo["MEMORY_1X"].get("XS"))
check_approx(T, "MEMORY_1X 4XL", 128.0, spo["MEMORY_1X"].get("4XL"))
# MEMORY_1X_x86
check_approx(T, "MEMORY_1X_x86 XS",  1.1,   spo["MEMORY_1X_x86"].get("XS"))
check_approx(T, "MEMORY_1X_x86 4XL", 140.8, spo["MEMORY_1X_x86"].get("4XL"))
# MEMORY_16X
check_approx(T, "MEMORY_16X M",   6.0,   spo["MEMORY_16X"].get("M"))
check_approx(T, "MEMORY_16X 5XL", 384.0, spo["MEMORY_16X"].get("5XL"))
# MEMORY_16X_x86
check_approx(T, "MEMORY_16X_x86 M",   6.25,  spo["MEMORY_16X_x86"].get("M"))
check_approx(T, "MEMORY_16X_x86 4XL", 200.0, spo["MEMORY_16X_x86"].get("4XL"))
# MEMORY_64X (no 6XL in PDF)
check_approx(T, "MEMORY_64X L",   15.0,  spo["MEMORY_64X"].get("L"))
check_approx(T, "MEMORY_64X 4XL", 240.0, spo["MEMORY_64X"].get("4XL"))
# MEMORY_64X_x86
check_approx(T, "MEMORY_64X_x86 L",   16.0,  spo["MEMORY_64X_x86"].get("L"))
check_approx(T, "MEMORY_64X_x86 4XL", 256.0, spo["MEMORY_64X_x86"].get("4XL"))


# ---------------------------------------------------------------------------
# Table 1(d) – Interactive Warehouse
# ---------------------------------------------------------------------------
T = "Table 1(d)"
iw = {r["size"]: r["credits_per_hour"] for r in D["warehouses"]["interactive"]["data"]}
for size, exp in [("XS", 0.6), ("S", 1.2), ("M", 2.4), ("L", 4.8),
                  ("XL", 9.6), ("2XL", 19.2), ("3XL", 38.4), ("4XL", 76.8)]:
    check_approx(T, f"size={size}", exp, iw.get(size))


# ---------------------------------------------------------------------------
# Table 1(f) – Gen1 SPCS: CPU, HIGHMEM, GPU
# ---------------------------------------------------------------------------
T = "Table 1(f)"
cpu = {r["family"]: r["credits_per_hour"] for r in D["spcs"]["cpu"]["data"]}
for fam, exp in [("CPU_X64_XS", 0.06), ("CPU_X64_S", 0.11), ("CPU_X64_M", 0.22),
                 ("CPU_X64_SL", 0.41), ("CPU_X64_L", 0.83)]:
    check_approx(T, fam, exp, cpu.get(fam))

highmem = {r["family"]: r["credits_per_hour"] for r in D["spcs"]["highmem"]["data"]}
for fam, exp in [("HIGHMEM_X64_S", 0.28), ("HIGHMEM_X64_M", 1.11),
                 ("HIGHMEM_X64_SL", 2.93), ("HIGHMEM_X64_L", 4.44)]:
    check_approx(T, fam, exp, highmem.get(fam))

gpu = {r["family"]: r["credits_per_hour"] for r in D["spcs"]["gpu"]["data"]}
for fam, exp in [
    ("GPU_NV_XS", 0.25), ("GPU_GCP_NV_L4_1_24G", 0.43), ("GPU_NV_S", 0.57),
    ("GPU_NV_SM", 1.70), ("GPU_GCP_NV_L4_4_24G", 1.94), ("GPU_NV_M", 2.68),
    ("GPU_NV_2M", 3.50), ("GPU_NV_3M", 3.55), ("GPU_GCP_NV_A100_8_40G", 11.68),
    ("GPU_NV_SL", 13.50), ("GPU_NV_L", 14.12),
]:
    check_approx(T, fam, exp, gpu.get(fam))

# Verify description labels are correct (bugs #1 and #2 from plan)
check_eq(T, "spcs.cpu description", "Table 1(f) - SPCS CPU Compute Credits/Hour",
         D["spcs"]["cpu"]["description"])
check_eq(T, "spcs.gpu description", "Table 1(f) - SPCS GPU Compute Credits/Hour",
         D["spcs"]["gpu"]["description"])
check_eq(T, "spcs.highmem description", "Table 1(f) - SPCS High-Memory Compute Credits/Hour",
         D["spcs"]["highmem"]["description"])


# ---------------------------------------------------------------------------
# Table 1(g) – Gen 2 SPCS
# ---------------------------------------------------------------------------
T = "Table 1(g)"
gen2spcs = {r["family"]: r for r in D["spcs"]["spcs_gen2"]["data"]}

for fam, aws, azure, gcp in [
    ("GEN_ARM_G1_2",  0.084, None, None),
    ("GEN_ARM_G1_4",  0.168, None, None),
    ("GEN_ARM_G1_8",  0.336, None, None),
    ("GEN_ARM_G1_16", 0.672, None, None),
    ("GEN_ARM_G1_32", 1.344, None, None),
    ("GEN_X64_G2_2",  0.092, 0.086, None),
    ("GEN_X64_G2_4",  0.184, 0.172, None),
    ("GEN_X64_G2_8",  0.368, 0.344, None),
    ("GEN_X64_G2_16", None,  0.688, None),
    ("GEN_X64_G2_32", 1.472, 1.376, None),
    ("GPU_L40S_G1_8",   1.580, None, None),
    ("GPU_L40S_G1_16",  3.160, None, None),
    ("GPU_L40S_G1_48",  9.480, None, None),
    ("GPU_L40S_G1_192", 37.920, None, None),
    ("GPU_R6K_G1_8",    2.537, None, None),
    ("GPU_R6K_G1_16",   5.074, None, None),
    ("GPU_R6K_G1_32",  10.148, None, None),
    ("GPU_R6K_G1_48",  15.222, None, None),
    ("GPU_R6K_G1_96",  30.444, None, None),
    ("GPU_R6K_G1_192", 60.888, None, None),
    ("GPU_A100_G1_12",  None, None, 5.051),
    ("GPU_A100_G1_48",  None, None, 20.204),
    ("MEM_X64_G2_8",   0.392, 0.311, None),
    ("MEM_X64_G2_32",  1.568, 1.244, None),
    ("MEM_X64_G2_64",  3.136, 2.486, None),
    ("MEM_X64_G2_96",  None,  3.732, None),
    ("MEM_X64_G2_192", 9.408, None,  None),
]:
    r = gen2spcs.get(fam, {})
    if aws is not None:
        check_approx(T, f"{fam} AWS", aws, r.get("aws"))
    if azure is not None:
        check_approx(T, f"{fam} Azure", azure, r.get("azure"))
    if gcp is not None:
        check_approx(T, f"{fam} GCP", gcp, r.get("gcp"))


# ---------------------------------------------------------------------------
# Table 1(h) – Snowflake Openflow
# ---------------------------------------------------------------------------
T = "Table 1(h)"
byoc = find_one(D["openflow"]["data"], deployment="BYOC")
if byoc:
    check_approx(T, "BYOC rate", 0.0225, byoc.get("rate"))
else:
    fail(T, "BYOC entry", "present", None)


# ---------------------------------------------------------------------------
# Table 1(i) – Snowflake Postgres Compute
# ---------------------------------------------------------------------------
T = "Table 1(i)"
pg = {r["family"]: r for r in D["postgres"]["data"]}

for fam, aws, azure, aws_ha, azure_ha in [
    ("STANDARD_M",    0.0356, 0.0376, 0.0712, 0.0752),
    ("STANDARD_L",    0.0712, 0.0752, 0.1424, 0.1504),
    ("STANDARD_XL",   0.1424, 0.1504, 0.2848, 0.3008),
    ("STANDARD_2X",   0.2848, 0.3008, 0.5696, 0.6016),
    ("STANDARD_4XL",  0.5696, 0.6016, 1.1392, 1.2032),
    ("STANDARD_8XL",  1.1392, 1.2032, 2.2784, 2.4064),
    ("STANDARD_12XL", 1.7088, 1.8048, 3.4176, 3.6096),
    ("STANDARD_24XL", 3.4176, 3.6096, 6.8352, 7.2192),
    ("HIGHMEM_L",     0.1024, 0.1088, 0.2048, 0.2176),
    ("HIGHMEM_XL",    0.2048, 0.2176, 0.4096, 0.4352),
    ("HIGHMEM_2XL",   0.4096, 0.4352, 0.8192, 0.8704),
    ("HIGHMEM_4XL",   0.8192, 0.8704, 1.6384, 1.7408),
    ("HIGHMEM_8XL",   1.6384, 1.7408, 3.2768, 3.4816),
    ("HIGHMEM_12XL",  2.4576, 2.6112, 4.9152, 5.2224),
    ("HIGHMEM_16XL",  3.2768, 3.4816, 6.5536, 6.9632),
    ("HIGHMEM_24XL",  4.9152, 5.2224, 9.8304, 10.4448),
    ("HIGHMEM_32XL",  6.5536, 6.9632, 13.1072, 13.9264),
    ("HIGHMEM_48XL",  9.8304, 10.4448, 19.6608, 20.8896),
    ("BURST_XS",      0.0068, None,    0.0136,  None),
    ("BURST_S",       0.0136, 0.0144, 0.0272,  0.0288),
    ("BURST_M",       0.0272, 0.0288, 0.0544,  0.0576),
]:
    r = pg.get(fam, {})
    check_approx(T, f"{fam} AWS", aws, r.get("aws"))
    check_approx(T, f"{fam} AWS_HA", aws_ha, r.get("aws_ha"))
    if azure is not None:
        check_approx(T, f"{fam} Azure", azure, r.get("azure"))
    if azure_ha is not None:
        check_approx(T, f"{fam} Azure_HA", azure_ha, r.get("azure_ha"))


# ---------------------------------------------------------------------------
# Table 2(a) – On-Demand Credit Pricing (spot checks, all 55 regions)
# ---------------------------------------------------------------------------
T = "Table 2(a)"
cp = {(r["cloud"], r["region"]): r for r in D["credit_pricing"]["data"]}

for cloud, region, std, ent, bc, vps in [
    ("AWS",   "US East (Northern Virginia)",    2.0,  3.0,  4.0,  6.0),
    ("AWS",   "US West (Oregon)",               2.0,  3.0,  4.0,  6.0),
    ("AWS",   "EU Dublin",                      2.6,  3.9,  5.2,  7.8),
    ("AWS",   "EU Frankfurt",                   2.6,  3.9,  5.2,  7.8),
    ("AWS",   "AP Sydney",                      2.75, 4.05, 5.5,  8.25),
    ("AWS",   "AP Singapore",                   2.5,  3.7,  5.0,  7.5),
    ("AWS",   "Canada Central",                 2.25, 3.5,  4.5,  6.75),
    ("AWS",   "US East 2 (Ohio)",               2.0,  3.0,  4.0,  6.0),
    ("AWS",   "AP Northeast 1 (Tokyo)",         2.85, 4.3,  5.7,  8.55),
    ("AWS",   "AP Mumbai",                      2.0,  3.0,  4.0,  6.0),
    ("AWS",   "US East 1 Commercial Gov",       None, None, 4.8,  7.2),
    ("AWS",   "Europe (London)",                2.7,  4.0,  5.4,  8.1),
    ("AWS",   "Asia Pacific (Seoul)",           2.75, 4.05, 5.5,  8.25),
    ("AWS",   "US Gov West 1",                  None, None, 5.6,  8.4),
    ("AWS",   "US Gov West 1 (Fedramp High Plus)", None, None, 5.6, 8.4),
    ("AWS",   "Europe (Stockholm)",             2.4,  3.6,  4.8,  7.2),
    ("AWS",   "Asia Pacific (Osaka)",           2.85, 4.3,  5.7,  8.55),
    ("AWS",   "South America East 1 (São Paulo)", 3.1, 4.65, 6.2, 9.3),
    ("AWS",   "EU (Paris)",                     2.6,  3.9,  5.2,  7.8),
    ("AWS",   "Asia Pacific (Jakarta)",         2.5,  3.7,  5.0,  7.5),
    ("AWS",   "US Gov East 1 (Fedramp High Plus)", None, None, 5.6, 8.4),
    ("AWS",   "EU (Zurich)",                    3.1,  4.65, 6.2,  9.3),
    ("AWS",   "US Gov West 1 (DoD)",            None, None, 5.6,  8.4),
    ("AWS",   "US West (Commercial Gov - Oregon)", None, None, 4.8, 7.2),
    ("AWS",   "Africa (Cape Town)",             2.8,  4.2,  5.6,  8.4),
    ("AWS",   "Middle East (UAE)",              2.7,  4.0,  5.4,  8.1),
    ("AWS",   "Asia Pacific (Malaysia)",        2.4,  3.6,  4.8,  7.2),
    ("AWS",   "Asia Pacific (Thailand)",        2.4,  3.6,  4.8,  7.2),
    ("Azure", "East US 2 (Virginia)",           2.0,  3.0,  4.0,  6.0),
    ("Azure", "West US 2 (Washington)",         2.0,  3.0,  4.0,  6.0),
    ("Azure", "West Europe (Netherlands)",      2.6,  3.9,  5.2,  7.8),
    ("Azure", "Australia East (New South Wales)", 2.75, 4.05, 5.5, 8.25),
    ("Azure", "Canada Central (Toronto)",       2.25, 3.5,  4.5,  6.75),
    ("Azure", "Southeast Asia (Singapore)",     2.5,  3.7,  5.0,  7.5),
    ("Azure", "Switzerland North",              3.1,  4.65, 6.2,  9.3),
    ("Azure", "US Gov Virginia",                None, None, 5.6,  8.4),
    ("Azure", "Central US (Iowa)",              2.0,  3.0,  4.0,  6.0),
    ("Azure", "North Europe (Ireland)",         2.6,  3.9,  5.2,  7.8),
    ("Azure", "Japan East (Tokyo)",             2.85, 4.3,  5.7,  8.55),
    ("Azure", "UAE North (Dubai)",              2.7,  4.0,  5.4,  8.1),
    ("Azure", "South Central US (Texas)",       2.0,  3.0,  4.0,  6.0),
    ("Azure", "Central India (Pune)",           2.0,  3.0,  4.0,  6.0),
    ("Azure", "UK South (London)",              2.7,  4.0,  5.4,  8.1),
    ("Azure", "US Gov Virginia (Fed Ramp High Plus)", None, None, 5.6, 8.4),
    ("Azure", "Mexico Central",                 2.0,  3.0,  4.0,  6.0),
    ("Azure", "Korea Central",                  2.75, 4.05, 5.5,  8.25),
    ("Azure", "Sweden Central",                 2.4,  3.6,  4.8,  7.2),
    ("Azure", "East US (Virginia)",             2.0,  3.0,  4.0,  6.0),
    ("GCP",   "US Central 1 (Iowa)",            2.0,  3.0,  4.0,  6.0),
    ("GCP",   "US East 4 (N. Virginia)",        2.0,  3.0,  4.0,  6.0),
    ("GCP",   "Europe West 4 (Netherlands)",    2.6,  3.9,  5.2,  7.8),
    ("GCP",   "Europe West 3 (Frankfurt)",      2.6,  3.9,  5.2,  7.8),
    ("GCP",   "Europe West 2 (London)",         2.7,  4.0,  5.4,  8.1),
    ("GCP",   "Middle East Central 2 (Dammam)", 3.25, 4.9,  6.5,  9.75),
    ("GCP",   "Australia Southeast 2 (Melbourne)", 2.75, 4.05, 5.5, 8.25),
]:
    r = cp.get((cloud, region), {})
    if std is not None:
        check_approx(T, f"{cloud} {region} standard", std, r.get("standard"))
    if ent is not None:
        check_approx(T, f"{cloud} {region} enterprise", ent, r.get("enterprise"))
    check_approx(T, f"{cloud} {region} business_critical", bc, r.get("business_critical"))
    check_approx(T, f"{cloud} {region} vps", vps, r.get("vps"))


# ---------------------------------------------------------------------------
# Table 2(b) – AI Credit Pricing
# ---------------------------------------------------------------------------
T = "Table 2(b)"
acp = D["ai_credit_pricing"]
check_approx(T, "on_demand global", 2.0, acp["on_demand"]["global"])
check_approx(T, "on_demand regional", 2.2, acp["on_demand"]["regional"])

tiers = {t["tier"]: t for t in acp["capacity_tiers"]}
for tier, g, r in [
    (1, 2.0,  2.2),
    (2, 1.96, 2.16),
    (3, 1.96, 2.16),
    (4, 1.94, 2.13),
    (5, 1.92, 2.11),
    (6, 1.9,  2.09),
    (7, 1.88, 2.07),
]:
    check_approx(T, f"tier {tier} global",   g, tiers.get(tier, {}).get("global"))
    check_approx(T, f"tier {tier} regional", r, tiers.get(tier, {}).get("regional"))


# ---------------------------------------------------------------------------
# Table 3(a) – Standard Storage (representative sample)
# ---------------------------------------------------------------------------
T = "Table 3(a)"
stor = {(r["cloud"], r["region"]): r for r in D["storage"]["standard"]["data"]}

for cloud, region, od, t1, t2, t3, t4, t5, t6, t7 in [
    ("AWS", "US East (Northern Virginia)",    23.0, 23.0, 21.47, 19.94, 18.4,  16.86, 15.34, 13.8),
    ("AWS", "EU Frankfurt",                   24.5, 24.5, 22.87, 21.24, 19.6,  17.96, 16.34, 14.7),
    ("AWS", "AP Sydney",                      25.0, 25.0, 23.33, 21.68, 20.0,  18.33, 16.68, 15.0),
    ("AWS", "Canada Central",                 25.0, 25.0, 23.33, 21.68, 20.0,  18.33, 16.68, 15.0),
    ("AWS", "US Gov West 1",                  39.0, 39.0, 36.4,  33.81, 31.2,  28.59, 26.01, 23.4),
    ("AWS", "South America East 1 (São Paulo)", 40.5, 40.5, 37.8, 35.11, 32.4, 29.69, 27.01, 24.3),
    ("AWS", "EU (Zurich)",                    26.95, 26.95, 25.15, 23.37, 21.56, 19.75, 17.98, 16.17),
    ("AWS", "Africa (Cape Town)",             27.4, 27.4, 25.57, 23.76, 21.92, 20.08, 18.28, 16.44),
    ("AWS", "Asia Pacific (Malaysia)",        22.5, 22.5, 21.0,  19.51, 18.0,  16.49, 15.01, 13.5),
    ("Azure", "East US 2 (Virginia)",         23.0, 23.0, 21.47, 19.94, 18.4,  16.86, 15.34, 13.8),
    ("Azure", "Switzerland North",            28.8, 28.8, 26.88, 24.97, 23.04, 21.11, 19.21, 17.28),
    ("Azure", "UAE North (Dubai)",            25.4, 25.4, 23.71, 22.02, 20.32, 18.62, 16.94, 15.24),
    ("GCP", "US Central 1 (Iowa)",            20.0, 20.0, 20.0,  20.0,  20.0,  20.0,  20.0,  20.0),
    ("GCP", "US East 4 (N. Virginia)",        23.0, 23.0, 23.0,  23.0,  23.0,  23.0,  23.0,  23.0),
    ("GCP", "Middle East Central 2 (Dammam)", 30.0, 30.0, 30.0,  30.0,  30.0,  30.0,  30.0,  30.0),
]:
    r = stor.get((cloud, region), {})
    check_approx(T, f"{cloud} {region} on_demand", od, r.get("on_demand"))
    for i, val in enumerate([t1, t2, t3, t4, t5, t6, t7], 1):
        check_approx(T, f"{cloud} {region} tier_{i}", val, r.get(f"tier_{i}"))


# ---------------------------------------------------------------------------
# Table 3(b) – Hybrid Tables Storage (spot checks)
# ---------------------------------------------------------------------------
T = "Table 3(b)"
ht = {(r["cloud"], r["region"]): r["rate_per_gb_month"]
      for r in D["storage"]["hybrid_tables"]["data"]}
for cloud, region, price in [
    ("AWS",   "US East (Northern Virginia)",   0.34),
    ("AWS",   "US West (Oregon)",              0.34),
    ("AWS",   "EU Dublin",                     0.34),
    ("AWS",   "EU Frankfurt",                  0.36),
    ("AWS",   "AP Sydney",                     0.37),
    ("AWS",   "AP Singapore",                  0.37),
    ("AWS",   "Canada Central",                0.37),
    ("AWS",   "US East 2 (Ohio)",              0.34),
    ("AWS",   "AP Northeast 1 (Tokyo)",        0.37),
    ("AWS",   "AP Mumbai",                     0.34),
    ("AWS",   "US Gov West 1",                 0.58),
    ("AWS",   "Europe (London)",               0.35),
    ("AWS",   "Asia Pacific (Seoul)",          0.37),
    ("AWS",   "South America East 1 (São Paulo)", 0.60),
    ("AWS",   "EU (Zurich)",                   0.40),
    ("Azure", "East US 2 (Virginia)",          0.34),
    ("Azure", "West US 2 (Washington)",        0.34),
    ("Azure", "West Europe (Netherlands)",     0.34),
    ("Azure", "Australia East (New South Wales)", 0.37),
    ("Azure", "Switzerland North",             0.43),
    ("Azure", "UAE North (Dubai)",             0.38),
    # GCP not listed in PDF Table 3(b); no entries expected in JSON
]:
    check_approx(T, f"{cloud} {region}", price, ht.get((cloud, region)))


# ---------------------------------------------------------------------------
# Table 3(c) – SPCS Block Storage (spot checks)
# ---------------------------------------------------------------------------
T = "Table 3(c)"
bs = {(r["cloud"], r["region"], r.get("instance_type", "CPU/GPU")): r
      for r in D["storage"]["spcs_block"]["data"]}

for cloud, region, itype, vol, iops, thru, snap in [
    ("AWS",   "US East (Northern Virginia)",   "CPU/GPU", 81.92,  5.0,  40.96, 51.2),
    ("AWS",   "EU Frankfurt",                  "CPU/GPU", 97.49,  6.0,  48.75, 55.3),
    ("AWS",   "AP Sydney",                     "CPU/GPU", 98.31,  6.0,  49.16, 56.3),
    ("AWS",   "South America East 1 (São Paulo)", "CPU/GPU", 155.65, 9.5, 77.83, 69.6),
    ("AWS",   "EU (Zurich)",                   "CPU/GPU", 116.95, 7.0,  58.48, 60.4),
    ("AWS",   "Africa (Cape Town)",            "CPU/GPU", 107.21, 6.5,  53.25, 60.93),
    ("Azure", "East US 2 (Virginia)",          "CPU/GPU", 82.23,  5.11, 41.12, 51.2),
    ("Azure", "Switzerland North",             "CPU/GPU", 117.37, 7.3,  58.31, 56.3),
    ("GCP",   "US Central 1 (Iowa)",           "CPU",     81.92,  5.0,  40.96, 51.2),
    ("GCP",   "US Central 1 (Iowa)",           "GPU",     81.92,  None, 122.88, 51.2),
    ("GCP",   "Middle East Central 2 (Dammam)", "CPU",    131.07, 8.0,  65.54, 81.92),
]:
    r = bs.get((cloud, region, itype), {})
    check_approx(T, f"{cloud} {region} {itype} volume", vol, r.get("volume_per_tb_month"))
    if iops is not None:
        check_approx(T, f"{cloud} {region} {itype} iops", iops, r.get("iops_per_1000_iops_month"))
    check_approx(T, f"{cloud} {region} {itype} throughput", thru, r.get("throughput_per_gb_sec_month"))
    check_approx(T, f"{cloud} {region} {itype} snapshot", snap, r.get("snapshot_per_tb_month"))


# ---------------------------------------------------------------------------
# Table 3(d) – ECO Cache
# ---------------------------------------------------------------------------
T = "Table 3(d)"
eco_data = D["storage"]["eco_cache"]["data"]
cloudflare = find_one(eco_data, provider="Cloudflare")
if cloudflare:
    check_approx(T, "Cloudflare ECO rate", 16.9, cloudflare.get("rate_per_tb_month"))
else:
    fail(T, "Cloudflare entry", "present", None)


# ---------------------------------------------------------------------------
# Table 3(e) – Archive Storage (spot checks)
# ---------------------------------------------------------------------------
T = "Table 3(e)"
arch = {(r["cloud"], r["region"]): r for r in D["storage"]["archive"]["data"]}

for cloud, region, cool_stor, cool_ret, cold_stor, cold_ret in [
    ("AWS",   "US East (Northern Virginia)",   4.0,  30.0, 1.0,  2.5),
    ("AWS",   "EU Dublin",                     4.0,  30.0, 1.0,  3.0),
    ("AWS",   "EU Frankfurt",                  5.0,  30.0, 1.0,  5.0),
    ("AWS",   "AP Sydney",                     5.0,  30.0, 1.0,  5.0),
    ("AWS",   "US Gov West 1",                 6.4,  30.0, 1.2,  3.4),
    ("AWS",   "South America East 1 (São Paulo)", 8.3, 30.0, 1.4, 8.0),
    ("AWS",   "EU (Zurich)",                   5.5,  30.0, 1.0,  5.0),
    ("AWS",   "Middle East (UAE)",             5.0,  30.0, 1.8,  3.3),
    ("Azure", "East US 2 (Virginia)",          4.0,  30.0, None, None),
    ("Azure", "Switzerland North",             5.71, 42.9, None, None),
    ("Azure", "US Gov Virginia",               6.4,  30.0, None, None),
    ("Azure", "South Central US (Texas)",      4.8,  36.0, None, None),
    ("GCP",   "US Central 1 (Iowa)",           4.0,  20.0, 1.2,  50.0),
    ("GCP",   "US East 4 (N. Virginia)",       6.0,  20.0, 2.5,  50.0),
    ("GCP",   "Middle East Central 2 (Dammam)", 6.0, 20.0, 2.7,  50.0),
]:
    r = arch.get((cloud, region), {})
    check_approx(T, f"{cloud} {region} cool_storage", cool_stor, r.get("cool_storage_per_tb_month"))
    check_approx(T, f"{cloud} {region} cool_retrieval", cool_ret, r.get("cool_retrieval_per_tb"))
    if cold_stor is not None:
        check_approx(T, f"{cloud} {region} cold_storage", cold_stor, r.get("cold_storage_per_tb_month"))
    if cold_ret is not None:
        check_approx(T, f"{cloud} {region} cold_retrieval", cold_ret, r.get("cold_retrieval_per_tb"))


# ---------------------------------------------------------------------------
# Table 3(f) – Postgres Storage (spot checks)
# ---------------------------------------------------------------------------
T = "Table 3(f)"
pgs = {(r["cloud"], r["region"]): r for r in D["storage"]["postgres"]["data"]}

for cloud, region, stor_val, ha_val in [
    ("AWS",   "US East (Northern Virginia)",   117.76, 235.52),
    ("AWS",   "EU Dublin",                     129.55, 259.10),
    ("AWS",   "EU Frankfurt",                  140.15, 280.30),
    ("AWS",   "AP Sydney",                     141.32, 282.64),
    ("AWS",   "AP Singapore",                  141.32, 282.64),
    ("AWS",   "Canada Central",                129.55, 259.10),
    ("AWS",   "US East 2 (Ohio)",              117.76, 235.52),
    ("AWS",   "AP Northeast 1 (Tokyo)",        141.32, 282.64),
    ("AWS",   "AP Mumbai",                     117.76, 235.52),
    ("AWS",   "Europe (London)",               136.60, 273.20),
    ("AWS",   "South America East 1 (São Paulo)", 223.74, 447.48),
    ("AWS",   "EU (Zurich)",                   168.11, 336.22),
    ("AWS",   "Africa (Cape Town)",            154.11, 308.22),
    ("AWS",   "Middle East (UAE)",             142.49, 284.98),
    ("Azure", "East US 2 (Virginia)",          118.21, 236.42),
    ("Azure", "West US 2 (Washington)",        118.16, 236.32),
    ("Azure", "Switzerland North",             168.71, 337.42),
    ("Azure", "US Gov Virginia",               141.85, 283.70),
    ("Azure", "UAE North (Dubai)",             142.91, 285.82),
    ("Azure", "East US (Virginia)",            119.23, 238.46),
]:
    r = pgs.get((cloud, region), {})
    check_approx(T, f"{cloud} {region} storage", stor_val, r.get("standard"))
    check_approx(T, f"{cloud} {region} HA", ha_val, r.get("high_availability"))


# ---------------------------------------------------------------------------
# Table 3(g) – Cloud Storage Requests (spot checks)
# ---------------------------------------------------------------------------
T = "Table 3(g)"
csr = {(r["cloud"], r["region"]): r for r in D["storage"]["cloud_storage_requests"]["data"]}

for cloud, region, c1, c2 in [
    ("AWS",   "US East (Northern Virginia)",   5.0,  0.40),
    ("AWS",   "EU Frankfurt",                  5.4,  0.43),
    ("AWS",   "AP Sydney",                     5.5,  0.44),
    ("AWS",   "Canada Central",                5.5,  0.44),
    ("AWS",   "AP Northeast 1 (Tokyo)",        4.7,  0.37),
    ("AWS",   "South America East 1 (São Paulo)", 7.0, 0.56),
    ("AWS",   "EU (Zurich)",                   5.4,  0.43),
    ("AWS",   "Africa (Cape Town)",            6.0,  0.40),
    ("AWS",   "Asia Pacific (Malaysia)",       4.5,  0.36),
    ("Azure", "East US 2 (Virginia)",          8.13, 0.52),
    ("Azure", "West Europe (Netherlands)",     8.78, 0.56),
    ("Azure", "Switzerland North",             8.78, 0.56),
    ("Azure", "US Gov Virginia",               10.2, 0.52),
    ("Azure", "UK South (London)",             9.59, 0.61),
    ("Azure", "UAE North (Dubai)",             8.12, 0.64),
    ("GCP",   "US Central 1 (Iowa)",           5.0,  0.40),
    ("GCP",   "Europe West 2 (London)",        5.0,  0.40),
    ("GCP",   "Middle East Central 2 (Dammam)", 5.0, 0.40),
]:
    r = csr.get((cloud, region), {})
    check_approx(T, f"{cloud} {region} class1", c1, r.get("class_1_per_million"))
    check_approx(T, f"{cloud} {region} class2", c2, r.get("class_2_per_million"))


# ---------------------------------------------------------------------------
# Table 4(a) – AWS Data Transfer (spot checks)
# ---------------------------------------------------------------------------
T = "Table 4(a)"
dt_aws = {r["region"]: r for r in D["data_transfer"]["aws"]["data"]}

for region, same, spcs, diff, inet in [
    ("US East (Northern Virginia)",    0.0, 3.07, 20,  90),
    ("AP Sydney",                      0.0, 3.07, 140, 140),
    ("AP Singapore",                   0.0, 3.07, 90,  120),
    ("AP Northeast 1 (Tokyo)",         0.0, 3.07, 90,  114),
    ("AP Mumbai",                      0.0, 3.07, 60,  90),
    ("Asia Pacific (Seoul)",           0.0, 3.07, 80,  126),
    ("US Gov West 1",                  0.0, 7.17, 30,  155),
    ("US Gov West 1 (Fedramp High Plus)", 0.0, 7.17, 30, 155),
    ("South America East 1 (São Paulo)", 0.0, 3.07, 138, 150),
    ("EU (Zurich)",                    0.0, 3.07, 20,  90),
    ("US Gov West 1 (DoD)",            0.0, 7.17, 30,  155),
    ("Africa (Cape Town)",             0.0, 3.07, 147, 154),
    ("Middle East (UAE)",              0.0, 3.07, 85,  110),
    ("Asia Pacific (Malaysia)",        0.0, 3.07, 80,  108),
    ("Asia Pacific (Thailand)",        0.0, 3.07, 80,  108),
]:
    r = dt_aws.get(region, {})
    check_approx(T, f"{region} same_region", same, r.get("same_region"))
    check_approx(T, f"{region} spcs_same_region", spcs, r.get("spcs_same_region"))
    check_approx(T, f"{region} different_region", diff, r.get("different_region"))
    check_approx(T, f"{region} internet", inet, r.get("internet"))


# ---------------------------------------------------------------------------
# Table 4(b) – Azure Data Transfer (spot checks)
# ---------------------------------------------------------------------------
T = "Table 4(b)"
dt_az = {r["region"]: r for r in D["data_transfer"]["azure"]["data"]}

for region, same, spcs, same_cont, diff_cont, diff_cloud in [
    ("East US 2 (Virginia)",     0.0, 0.0, 20,  50,  87.5),
    ("Australia East (New South Wales)", 0.0, 0.0, 80, 80, 120.0),
    ("Canada Central (Toronto)", 0.0, 0.0, 20,  50,  87.5),
    ("Southeast Asia (Singapore)", 0.0, 0.0, 80, 80, 120.0),
    ("Switzerland North",        0.0, 0.0, 20,  50,  87.5),
    ("US Gov Virginia",          0.0, 0.0, 20,  50,  87.5),
    ("Japan East (Tokyo)",       0.0, 0.0, 80,  80,  120.0),
    ("UAE North (Dubai)",        0.0, 0.0, 80,  80,  120.0),
    ("Central India (Pune)",     0.0, 0.0, 40,  50,  87.5),
    ("Mexico Central",           0.0, 0.0, 20,  50,  87.0),
    ("Korea Central",            0.0, 0.0, 80,  80,  120.0),
    ("Sweden Central",           0.0, 0.0, 20,  50,  87.0),
    ("East US (Virginia)",       0.0, 0.0, 20,  50,  87.0),
]:
    r = dt_az.get(region, {})
    check_approx(T, f"{region} same_region", same, r.get("same_region"))
    check_approx(T, f"{region} spcs_same_region", spcs, r.get("spcs_same_region"))
    check_approx(T, f"{region} same_continent", same_cont, r.get("same_continent"))
    check_approx(T, f"{region} different_continent", diff_cont, r.get("different_continent"))
    check_approx(T, f"{region} internet", diff_cloud, r.get("internet"))


# ---------------------------------------------------------------------------
# Table 4(c) – GCP Data Transfer (spot checks)
# ---------------------------------------------------------------------------
T = "Table 4(c)"
dt_gcp = {r["region"]: r for r in D["data_transfer"]["gcp"]["data"]}

# Same-cloud geo breakdown
for region, na, eu, asia, indonesia, me, oceania, africa, sa in [
    ("US Central 1 (Iowa)",           20, 50, 80, 100, 110, 100, 110, 140),
    ("US East 4 (N. Virginia)",       20, 50, 80, 100, 110, 100, 110, 140),
    ("Europe West 4 (Netherlands)",   50, 20, 80, 100, 110, 100, 110, 140),
    ("Europe West 2 (London)",        50, 20, 80, 100, 110, 100, 110, 140),
    ("Europe West 3 (Frankfurt)",     50, 20, 80, 100, 110, 100, 110, 140),
    ("Middle East Central 2 (Dammam)", 110, 110, 110, 110, 80, 110, 110, 110),
    ("Australia Southeast 2 (Melbourne)", 100, 100, 100, 80, 110, 80, 140, 140),
]:
    r = dt_gcp.get(region, {})
    sc = r.get("same_cloud", {})
    check_approx(T, f"{region} NA", na, sc.get("north_america"))
    check_approx(T, f"{region} EU", eu, sc.get("europe"))
    check_approx(T, f"{region} Asia", asia, sc.get("asia"))

# Different-cloud/internet
for region, n_am, eu, asia_val, austr_korea_sa, me_africa, china in [
    ("US Central 1 (Iowa)",           120, 120, 120, 190, 150, 230),
    ("Europe West 4 (Netherlands)",   120, 120, 120, 190, 150, 230),
    ("Middle East Central 2 (Dammam)", 190, 190, 190, 190, 190, 230),
    ("Australia Southeast 2 (Melbourne)", 190, 190, 190, 190, 190, 230),
]:
    r = dt_gcp.get(region, {})
    dco = r.get("different_cloud_or_internet", {})
    check_approx(T, f"{region} diff_cloud NA", n_am, dco.get("north_america"))
    check_approx(T, f"{region} diff_cloud EU", eu, dco.get("europe"))


# ---------------------------------------------------------------------------
# Table 4(d) – Endpoint Types
# ---------------------------------------------------------------------------
T = "Table 4(d)"
ep_data = D["data_transfer"].get("specific_endpoints", {}).get("data", [])
aws_gw = find_one(ep_data, endpoint_type="AWS API Gateway, Private Endpoints")
if aws_gw:
    check_approx(T, "AWS API Gateway $/TB", 10.0, aws_gw.get("rate_per_tb"))
else:
    fail(T, "AWS API Gateway Private Endpoints entry", "present", None)


# ---------------------------------------------------------------------------
# Table 4(e) – Outbound Privatelink (spot checks)
# ---------------------------------------------------------------------------
T = "Table 4(e)"
pl = {(r["cloud"], r["region"]): r for r in D["data_transfer"]["privatelink"]["data"]}

for cloud, region, endpoint, first_1pb, next_4pb, over_5pb in [
    ("AWS",   "US East (Northern Virginia)",   10.0,  10.24, 6.14, 4.09),
    ("AWS",   "EU Dublin",                     11.0,  10.24, 6.14, 4.09),
    ("AWS",   "EU Frankfurt",                  12.0,  10.24, 6.14, 4.09),
    ("AWS",   "AP Sydney",                     13.0,  10.24, 6.14, 4.09),
    ("AWS",   "AP Singapore",                  13.0,  10.24, 6.14, 4.09),
    ("AWS",   "AP Northeast 1 (Tokyo)",        14.0,  10.24, 6.14, 4.09),
    ("AWS",   "US Gov West 1",                 12.5,  10.24, 6.14, 4.09),
    ("AWS",   "South America East 1 (São Paulo)", 21.0, 10.24, 6.14, 4.09),
    ("AWS",   "EU (Zurich)",                   13.2,  10.24, 6.14, 4.09),
    ("AWS",   "Africa (Cape Town)",            13.09, 10.24, 6.14, 4.09),
    ("Azure", "East US 2 (Virginia)",          10.0,  10.24, 6.14, 4.09),
    ("Azure", "US Gov Virginia",               13.0,  12.80, 12.80, 12.80),
    ("Azure", "US Gov Virginia (Fed Ramp High Plus)", 13.0, 12.80, 12.80, 12.80),
    ("GCP",   "US Central 1 (Iowa)",           10.0,  30.72, 26.62, 24.57),
    ("GCP",   "Middle East Central 2 (Dammam)", 10.0, 30.72, 26.62, 24.57),
]:
    r = pl.get((cloud, region), {})
    check_approx(T, f"{cloud} {region} endpoint_per_1k_hrs", endpoint, r.get("endpoint_fee_per_1k_hours"))
    check_approx(T, f"{cloud} {region} first_1pb", first_1pb, r.get("data_first_1pb_per_tb"))
    check_approx(T, f"{cloud} {region} next_4pb", next_4pb, r.get("data_next_4pb_per_tb"))
    check_approx(T, f"{cloud} {region} over_5pb", over_5pb, r.get("data_over_5pb_per_tb"))


# ---------------------------------------------------------------------------
# Table 5 – Serverless Feature Table
# ---------------------------------------------------------------------------
T = "Table 5"
mults = {r["feature"]: r for r in D["serverless"]["multipliers"]}
units = {r["feature"]: r for r in D["serverless"]["unit_charges"]}

# Multipliers from PDF Table 5
for feat, comp, cloud_svc in [
    ("Backup",                   2.0, 1.0),
    ("Clustered Tables",         2.0, 1.0),
    ("Data Quality Monitoring",  2.0, 1.0),
    ("Failsafe Recovery",        0.9, 1.0),
    ("Materialized Views",       2.0, 1.0),
    ("Query Acceleration",       1.0, None),
    ("Replication",              2.0, 0.35),
    ("Search Optimization",      2.0, 1.0),
    ("Sensitive Data Classification", 0.9, 1.0),
    ("Serverless Alerts",        0.9, 1.0),
    ("Serverless Tasks",         0.9, 1.0),
    ("Serverless Tasks Flex",    0.5, 1.0),
    ("Storage Lifecycle Policy Execution", 0.5, 1.0),
    ("Table Optimization",       0.75, 1.0),
    ("Trust Center",             1.0, 1.0),
    ("Logging",                  1.25, None),
    ("Snowpipe Streaming Classic", 1.0, None),
]:
    r = mults.get(feat, {})
    check_approx(T, f"{feat} compute_multiplier", comp, r.get("compute_multiplier"))
    if cloud_svc is not None:
        check_approx(T, f"{feat} cloud_services_multiplier", cloud_svc, r.get("cloud_services_multiplier"))

# Unit charges from PDF Table 5
for feat, rate, unit_substr in [
    ("Snowpipe",                 0.0037, "GB"),
    ("Snowpipe Streaming",       0.0037, "uncompressed"),
    ("Telemetry Data Ingest",    0.0212, "GB"),
    ("Open Catalog",             0.5,    "1M"),
    ("Archive Storage Retrieval File Processing", 0.05, "1000 files"),
    ("Archive Storage Write",    0.05,   "1000 files"),
    ("Logging",                  0.28,   "1000 file batches"),
    ("Snowpipe Streaming Classic", 0.01, "client instance"),
]:
    r = units.get(feat, {})
    check_approx(T, f"{feat} rate", rate, r.get("rate"))


# ---------------------------------------------------------------------------
# Table 6(a) – Cortex AI Functions (current models)
# ---------------------------------------------------------------------------
T = "Table 6(a)"
cc = {r["model"]: r for r in D["ai_features"]["cortex_complete"]["data"]}

for model, inp, out in [
    ("claude-haiku-4-5",         0.55, 2.75),
    ("claude-opus-4-5",          2.75, 13.75),
    ("claude-opus-4-6",          2.75, 13.75),
    ("claude-opus-4-7",          2.75, 13.75),
    ("claude-sonnet-4-5",        1.65, 8.25),
    ("claude-sonnet-4-5-long-context", 3.3, 12.38),
    ("claude-sonnet-4-6",        1.65, 8.25),
    ("deepseek-r1",              0.68, 2.70),
    ("gemini-2-5-flash",         0.15, 1.25),
    ("gemini-2-5-flash-lite",    0.05, 0.20),
    ("gemini-3.1-pro",           1.1,  6.60),
    ("gemini-3.1-pro-long-context", 2.2, 9.9),
    ("llama3.1-405b",            1.2,  1.20),
    ("llama3.1-70b",             0.36, 0.36),
    ("llama3.1-8b",              0.11, 0.11),
    ("llama3.3-70b",             0.36, 0.36),
    ("llama4-maverick",          0.12, 0.49),
    ("llama4-scout",             0.09, 0.33),
    ("mistral-large2",           1.0,  3.0),
    ("mistral-7b",               0.08, 0.10),
    ("mixtral-8x7b",             0.23, 0.35),
    ("openai-gpt-4.1",           1.0,  4.0),
    ("openai-gpt-5",             0.69, 5.5),
    ("openai-gpt-5-mini",        0.14, 1.1),
    ("openai-gpt-5-nano",        0.03, 0.22),
    ("openai-gpt-5.1",           0.69, 5.5),
    ("openai-gpt-5.2",           0.97, 7.7),
    ("openai-gpt-5.4",           1.38, 8.25),
    ("openai-gpt-5.4-long-context", 2.75, 12.38),
    ("openai-gpt-5.5",           2.75, 16.5),
    ("openai-gpt-5.5-long-context", 5.5, 24.75),
    ("pixtral-large",            1.0,  3.0),
    ("snowflake-llama-3.1-405b", 0.96, 0.96),
    ("snowflake-llama-3.3-70b",  0.29, 0.29),
]:
    r = cc.get(model, {})
    check_approx(T, f"{model} input", inp, r.get("input"))
    check_approx(T, f"{model} output", out, r.get("output"))

# Utility functions
uf = {r["function"]: r["rate"] for r in D["ai_features"]["utility_functions"]["data"]}
for func, rate in [
    ("AI_AGG",          1.60),
    ("AI_CLASSIFY",     1.39),
    ("AI_EXTRACT (arctic-extract)", 5.0),
    ("AI_FILTER",       1.39),
    ("AI_GUARDRAILS",   0.35),
    ("AI_REDACT",       0.63),
    ("AI Sentiment",    1.60),
    ("AI_SUMMARIZE_AGG", 1.60),
    ("AI_TRANSCRIBE",   1.30),
    ("AI_TRANSLATE",    1.50),
    ("Extract Answer",  0.08),
    ("Guard",           0.25),
    ("Sentiment",       0.08),
    ("Summarize",       0.10),
]:
    check_approx(T, f"utility {func}", rate, uf.get(func))

# Verify spurious "Translate" duplicate is gone (bug #4 from plan)
if "Translate" in uf:
    fail(T, "spurious 'Translate' entry", "absent", uf["Translate"])

# Embeddings
emb = {r["model"]: r["rate"] for r in D["ai_features"]["embeddings"]["data"]}
for model, rate in [
    ("voyage-multimodal-3",            0.06),
    ("multilingual-e5-large",          0.05),
    ("nv-embed-qa-4",                  0.05),
    ("snowflake-arctic-embed-l-v2.0",  0.05),
    ("voyage-multilingual-2",          0.07),
    ("e5-base-v2",                     0.03),
    ("snowflake-arctic-embed-m",       0.03),
    ("snowflake-arctic-embed-m-v1.5",  0.03),
]:
    check_approx(T, f"embed {model}", rate, emb.get(model))


# ---------------------------------------------------------------------------
# Table 6(b) – REST API with Prompt Caching (spot checks)
# ---------------------------------------------------------------------------
T = "Table 6(b)"
rac = D["ai_features"]["rest_api_with_caching"]["data"]
rac_idx = {}
for r in rac:
    rac_idx[(r["model"], r["inference_region"])] = r

for model, region, inp, out, cw, cr in [
    ("claude-4-sonnet",    "AWS Regional", 3.0,  15.0,  3.75, 0.30),
    ("claude-sonnet-4-5",  "AWS Regional", 3.3,  16.5,  4.13, 0.33),
    ("claude-sonnet-4-5",  "AWS Global",   3.0,  15.0,  3.75, 0.30),
    ("claude-sonnet-4-6",  "AWS Regional", 3.3,  16.5,  4.13, 0.33),
    ("claude-haiku-4-5",   "AWS Regional", 1.1,  5.5,   1.38, 0.11),
    ("claude-haiku-4-5",   "AWS Global",   1.0,  5.0,   1.25, 0.10),
    ("claude-opus-4-5",    "AWS Regional", 5.5,  27.5,  6.88, 0.55),
    ("openai-gpt-4.1",     "Azure Regional", 2.2, 8.8,  None, 0.55),
    ("openai-gpt-4.1",     "Azure Global",   2.0, 8.0,  None, 0.50),
    ("openai-gpt-5",       "Azure Regional", 1.38, 11.0, None, 0.14),
    ("openai-gpt-5.2",     "Azure Regional", 1.93, 15.4, None, 0.19),
    ("openai-gpt-5.4",     "Azure Regional", 2.75, 16.5, None, 0.28),
    ("openai-gpt-5.5",     "Azure Regional", 5.5, 33.0,  None, 0.55),
    ("openai-gpt-5.5-long-context", "Azure Regional", 11.0, 49.5, None, 1.10),
]:
    r = rac_idx.get((model, region), {})
    check_approx(T, f"{model} {region} input",  inp, r.get("input"))
    check_approx(T, f"{model} {region} output", out, r.get("output"))
    if cw is not None:
        check_approx(T, f"{model} {region} cache_write", cw, r.get("cache_write"))
    check_approx(T, f"{model} {region} cache_read", cr, r.get("cache_read"))


# ---------------------------------------------------------------------------
# Table 6(c) – REST API OSS
# ---------------------------------------------------------------------------
T = "Table 6(c)"
oss = {r["model"]: r for r in D["ai_features"]["rest_api_oss"]["data"]}

for model, inp, out in [
    ("deepseek-r1",          1.35, 5.40),
    ("llama3.1-405b",        2.40, 2.40),
    ("llama3.1-70b",         0.72, 0.72),
    ("llama3.1-8b",          0.22, 0.22),
    ("llama3.2-1b",          0.10, 0.10),
    ("llama3.2-3b",          0.15, 0.15),
    ("llama3.3-70b",         0.72, 0.72),
    ("llama4-maverick",      0.24, 0.97),
    ("mistral-large",        4.0,  12.0),
    ("mistral-large2",       2.0,  6.0),
    ("mistral-7b",           0.15, 0.20),
    ("snowflake-llama-3.3-70b", 0.72, 0.72),
]:
    r = oss.get(model, {})
    check_approx(T, f"{model} input",  inp, r.get("input"))
    check_approx(T, f"{model} output", out, r.get("output"))


# ---------------------------------------------------------------------------
# Table 6(d) – Intelligence/Agents/Analyst
# ---------------------------------------------------------------------------
T = "Table 6(d)"
ia = {r["model"]: r for r in D["ai_features"]["intelligence_agents_analyst"]["data"]}

for model, inp, out, cw, cr in [
    ("claude-4-sonnet",    1.77, 8.87,  2.22, 0.18),
    ("claude-haiku-4-5",   0.65, 3.25,  0.81, 0.06),
    ("claude-opus-4-5",    3.25, 16.26, 4.07, 0.33),
    ("claude-opus-4-6",    3.25, 16.26, 4.07, 0.33),
    ("claude-sonnet-4-5",  1.95, 9.76,  2.44, 0.20),
    ("claude-sonnet-4-6",  1.95, 9.76,  2.44, 0.20),
    ("openai-gpt-4.1",     1.30, 5.20,  None, 0.33),
    ("openai-gpt-5",       0.81, 6.51,  None, 0.08),
    ("openai-gpt-5.1",     0.81, 6.51,  None, 0.08),
    ("openai-gpt-5.2",     1.14, 9.11,  None, 0.11),
    ("openai-gpt-5.4",     1.63, 9.76,  None, 0.16),
    ("openai-gpt-5.5",     3.25, 19.50, None, 0.33),
    ("openai-gpt-5.5-long-context", 6.50, 29.25, None, 0.65),
]:
    r = ia.get(model, {})
    check_approx(T, f"{model} input",  inp, r.get("input"))
    check_approx(T, f"{model} output", out, r.get("output"))
    if cw is not None:
        check_approx(T, f"{model} cache_write", cw, r.get("cache_write"))
    check_approx(T, f"{model} cache_read", cr, r.get("cache_read"))


# ---------------------------------------------------------------------------
# Table 6(e) – Cortex Code
# ---------------------------------------------------------------------------
T = "Table 6(e)"
ccode = {r["model"]: r for r in D["ai_features"]["cortex_code"]["data"]}

for model, inp, out, cw, cr in [
    ("claude-4-sonnet",    1.50, 7.50,  1.88, 0.15),
    ("claude-opus-4-5",    2.75, 13.75, 3.44, 0.28),
    ("claude-opus-4-6",    2.75, 13.75, 3.44, 0.28),
    ("claude-sonnet-4-5",  1.65, 8.25,  2.07, 0.17),
    ("claude-sonnet-4-6",  1.65, 8.25,  2.07, 0.17),
    ("openai-gpt-5.2",     0.97, 7.70,  None, 0.10),
    ("openai-gpt-5.4",     1.38, 8.25,  None, 0.14),
    ("openai-gpt-5.5",     2.75, 16.50, None, 0.28),
    ("openai-gpt-5.5-long-context", 5.50, 24.75, None, 0.55),
]:
    r = ccode.get(model, {})
    check_approx(T, f"{model} input",  inp, r.get("input"))
    check_approx(T, f"{model} output", out, r.get("output"))
    if cw is not None:
        check_approx(T, f"{model} cache_write", cw, r.get("cache_write"))
    if cr is not None:
        check_approx(T, f"{model} cache_read", cr, r.get("cache_read"))


# ---------------------------------------------------------------------------
# Table 6(f) – Fine-tuning
# ---------------------------------------------------------------------------
T = "Table 6(f)"
ft = {r["model"]: r for r in D["ai_features"]["fine_tuning"]["data"]}

for model, train, infer in [
    ("arctic-extract-finetuned", 0,    10),
    ("llama3.1-70b",             3.40, 2.42),
    ("llama3.1-8b",              0.64, 0.38),
    ("mistral-7b",               0.64, 0.24),
    ("mixtral-8x7b",             3.40, 0.44),
]:
    r = ft.get(model, {})
    check_approx(T, f"{model} training",   train, r.get("training"))
    check_approx(T, f"{model} inference",  infer, r.get("inference"))


# ---------------------------------------------------------------------------
# Table 6(g) – Other AI Features
# ---------------------------------------------------------------------------
T = "Table 6(g)"
oai = {r["feature"]: r for r in D["ai_features"]["other_ai_features"]["data"]}

for feat, rate, unit_substr in [
    ("AI Parse Document - Layout",  3.33, "1,000 pages"),
    ("AI Parse Document - OCR",     0.5,  "1,000 pages"),
    ("Batch Cortex Search",         0.12, "GB/hr"),
    ("Cortex Analyst (API)",        67.0, "1,000 messages"),
    ("Cortex Search",               6.3,  "GB/mo"),
    ("Document AI",                 8.0,  "hour"),
]:
    r = oai.get(feat, {})
    check_approx(T, feat, rate, r.get("rate"))

# Verify description label is correct (bug #3 from plan)
check_eq(T, "other_ai_features description", "Table 6(g) - Other AI Features",
         D["ai_features"]["other_ai_features"]["description"])


# ---------------------------------------------------------------------------
# Table 6(h) – Provisioned Throughput
# ---------------------------------------------------------------------------
T = "Table 6(h)"
pt = {r["cloud"]: r for r in D["ai_features"]["provisioned_throughput"]["data"]}
check_approx(T, "AWS credits_per_ptu_per_hour",   0.08, pt.get("AWS", {}).get("credits_per_ptu_per_hour"))
check_approx(T, "Azure credits_per_ptu_per_hour",  0.10, pt.get("Azure", {}).get("credits_per_ptu_per_hour"))
check_eq(T, "AWS term_length_months",   1, pt.get("AWS", {}).get("term_length_months"))
check_eq(T, "Azure term_length_months", 1, pt.get("Azure", {}).get("term_length_months"))


# ---------------------------------------------------------------------------
# Table 7 – Openflow Connector for Oracle
# ---------------------------------------------------------------------------
T = "Table 7"
ofo = {r["component"]: r["rate_per_core_month"] for r in D["openflow_oracle"]["data"]}
check_approx(T, "License $/core/mo",             70.0, ofo.get("License"))
check_approx(T, "Support & Maintenance $/core/mo", 40.0, ofo.get("Support & Maintenance"))


# ---------------------------------------------------------------------------
# Table 8 – Organization Usage
# ---------------------------------------------------------------------------
T = "Table 8"
ou = {r["label"]: r["credits"] for r in D["organization_usage"]["data"]}
for label, credits in [
    ("< 1 million",                          0),
    ("1 million ≤ Records < 10 million", 2),
    ("10 million ≤ Records < 50 million", 11),
    ("50 million ≤ Records < 250 million", 50),
    ("250 million ≤ Records < 500 million", 115),
    ("500 million ≤ Records < 1 billion", 230),
    ("1 billion ≤ Records < 2.5 billion", 290),
    ("2.5 billion ≤ Records < 5 billion", 575),
    ("5 billion ≤ Records < 10 billion", 1150),
    ("10 billion ≤ Records < 20 billion", 2300),
    ("20 billion ≤ Records",              3500),
]:
    check_eq(T, label, credits, ou.get(label))


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
if warnings:
    print(f"\nWARNINGS ({len(warnings)}):")
    for w in warnings:
        print(f"  ⚠  {w}")

if errors:
    print(f"\nFAILURES ({len(errors)}):")
    for e in errors:
        print(f"  ✗  {e}")
    print(f"\n{len(errors)} discrepancies found.")
    sys.exit(1)
else:
    print(f"✓ All checks passed ({len(errors)} errors, {len(warnings)} warnings).")
    sys.exit(0)
