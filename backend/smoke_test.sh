#!/bin/bash
# End-to-end smoke test against a live server (default port 8321).
set -e
BASE=${1:-http://127.0.0.1:8321}
JAR=/tmp/awp_smoke.txt
rm -f $JAR

j() { python3 -c "import sys,json;d=json.load(sys.stdin);print(d$1)"; }

echo "== 1. Setup admin =="
curl -s -c $JAR -X POST $BASE/api/auth/setup -H 'Content-Type: application/json' \
  -d '{"username":"admin","full_name":"Admin","password":"admin123","password_confirm":"admin123"}' | j "['user']['username']"

echo "== 2. Login =="
TOKEN=$(curl -s -X POST $BASE/api/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | j "['access_token']")
AUTH="Authorization: Bearer $TOKEN"

echo "== 3. Create customer + vehicle =="
CID=$(curl -s -H "$AUTH" -X POST $BASE/api/customers -H 'Content-Type: application/json' \
  -d '{"name":"Ali Khan","phone":"03001234567"}' | j "['id']")
VID=$(curl -s -H "$AUTH" -X POST $BASE/api/vehicles -H 'Content-Type: application/json' \
  -d "{\"customer_id\":$CID,\"vehicle_type\":\"motorcycle\",\"registration_no\":\"KHI-1234\",\"make\":\"Honda\",\"model\":\"CG-125\",\"year\":2019,\"odometer\":12500}" | j "['id']")
echo "customer=$CID vehicle=$VID"

echo "== 4. Category + product =="
CATID=$(curl -s -H "$AUTH" -X POST $BASE/api/categories -H 'Content-Type: application/json' \
  -d '{"name":"Spark Plugs"}' | j "['id']")
PID=$(curl -s -H "$AUTH" -X POST $BASE/api/products -H 'Content-Type: application/json' \
  -d "{\"name\":\"NGK Spark Plug\",\"sku\":\"NGK-CPR8\",\"barcode\":\"8859110\",\"category_id\":$CATID,\"purchase_cost_paisa\":12000,\"selling_price_paisa\":25000,\"min_stock\":5,\"unit\":\"pcs\"}" | j "['id']")
echo "category=$CATID product=$PID"

echo "== 5. Supplier + purchase + receive (stock +10 exactly once) =="
SUPID=$(curl -s -H "$AUTH" -X POST $BASE/api/suppliers -H 'Content-Type: application/json' \
  -d '{"name":"Auto Parts Depot","phone":"021-1234567"}' | j "['id']")
POID=$(curl -s -H "$AUTH" -X POST $BASE/api/purchases -H 'Content-Type: application/json' \
  -d "{\"supplier_id\":$SUPID,\"items\":[{\"product_id\":$PID,\"quantity\":10,\"unit_cost_paisa\":12000}]}" | j "['id']")
curl -s -H "$AUTH" -X POST $BASE/api/purchases/$POID/receive -H 'Content-Type: application/json' \
  -d "{\"items\":[{\"product_id\":$PID,\"quantity\":10}]}" > /dev/null
STOCK=$(curl -s -H "$AUTH" "$BASE/api/products?q=NGK" | j "['items'][0]['quantity_on_hand']")
echo "stock after receive: $STOCK (expect 10)"
[ "$STOCK" = "10" ] || { echo "FAIL: stock $STOCK"; exit 1; }

echo "== 6. Service catalog + mechanic =="
SVCID=$(curl -s -H "$AUTH" -X POST $BASE/api/services -H 'Content-Type: application/json' \
  -d '{"name":"General bike service","code":"SVC-GEN","default_charge_paisa":80000,"estimated_minutes":60}' | j "['id']")
MECHID=$(curl -s -H "$AUTH" -X POST $BASE/api/mechanics -H 'Content-Type: application/json' \
  -d '{"name":"Raza Mechanic","skill":"Engine"}' | j "['id']")

echo "== 7. Job card workflow =="
JOBID=$(curl -s -H "$AUTH" -X POST $BASE/api/jobs -H 'Content-Type: application/json' \
  -d "{\"customer_id\":$CID,\"vehicle_id\":$VID,\"reported_issue\":\"Bike not starting\",\"complaint\":\"Hard start\",\"est_labor_paisa\":80000,\"est_parts_paisa\":25000,\"mechanic_id\":$MECHID}" | j "['id']")
curl -s -H "$AUTH" -X POST $BASE/api/jobs/$JOBID/services -H 'Content-Type: application/json' \
  -d "{\"service_id\":$SVCID,\"description\":\"General bike service\",\"quantity\":1,\"unit_charge_paisa\":80000}" > /dev/null
curl -s -H "$AUTH" -X POST $BASE/api/jobs/$JOBID/parts -H 'Content-Type: application/json' \
  -d "{\"product_id\":$PID,\"quantity\":1,\"unit_price_paisa\":25000}" > /dev/null
STOCK2=$(curl -s -H "$AUTH" "$BASE/api/products?q=NGK" | j "['items'][0]['quantity_on_hand']")
echo "stock after job part: $STOCK2 (expect 9)"
[ "$STOCK2" = "9" ] || { echo "FAIL: stock $STOCK2"; exit 1; }
# invalid transition must be rejected (received -> in_progress is not allowed)
BAD=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH" -X POST $BASE/api/jobs/$JOBID/status -H 'Content-Type: application/json' \
  -d '{"status":"in_progress"}')
[ "$BAD" = "400" ] || { echo "FAIL: invalid transition accepted ($BAD)"; exit 1; }
# walk the real workflow: inspection -> awaiting_approval -> approved -> in_progress -> completed
for ST in inspection awaiting_approval; do
  S=$(curl -s -H "$AUTH" -X POST $BASE/api/jobs/$JOBID/status -H 'Content-Type: application/json' \
    -d "{\"status\":\"$ST\"}" | j "['status']")
  [ "$S" = "$ST" ] || { echo "FAIL: status $ST got $S"; exit 1; }
done
curl -s -H "$AUTH" -X POST $BASE/api/jobs/$JOBID/approval -H 'Content-Type: application/json' \
  -d '{"approval_status":"approved"}' > /dev/null
for ST in approved in_progress completed ready_for_delivery; do
  S=$(curl -s -H "$AUTH" -X POST $BASE/api/jobs/$JOBID/status -H 'Content-Type: application/json' \
    -d "{\"status\":\"$ST\"}" | j "['status']")
  [ "$S" = "$ST" ] || { echo "FAIL: status $ST got $S"; exit 1; }
done
# completion must be blocked while the estimate approval is pending
JOB2=$(curl -s -H "$AUTH" -X POST $BASE/api/jobs -H 'Content-Type: application/json' \
  -d "{\"customer_id\":$CID,\"vehicle_id\":$VID,\"reported_issue\":\"Second job\",\"est_labor_paisa\":1000,\"est_parts_paisa\":0}" | j "['id']")
curl -s -H "$AUTH" -X POST $BASE/api/jobs/$JOB2/status -H 'Content-Type: application/json' \
  -d '{"status":"inspection"}' > /dev/null
curl -s -H "$AUTH" -X POST $BASE/api/jobs/$JOB2/status -H 'Content-Type: application/json' \
  -d '{"status":"awaiting_approval"}' > /dev/null
curl -s -H "$AUTH" -X POST $BASE/api/jobs/$JOB2/status -H 'Content-Type: application/json' \
  -d '{"status":"approved"}' > /dev/null
curl -s -H "$AUTH" -X POST $BASE/api/jobs/$JOB2/status -H 'Content-Type: application/json' \
  -d '{"status":"in_progress"}' > /dev/null
GATE=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH" -X POST $BASE/api/jobs/$JOB2/status -H 'Content-Type: application/json' \
  -d '{"status":"completed"}')
[ "$GATE" = "400" ] || { echo "FAIL: completion without estimate approval allowed ($GATE)"; exit 1; }
echo "job $JOBID: received → inspection → awaiting_approval → approved → in_progress → completed → ready_for_delivery OK"
echo "approval gate enforced on job $JOB2 (completion blocked until estimate approved)"

echo "== 8. POS invoice (workflow A) =="
INV=$(curl -s -H "$AUTH" -X POST $BASE/api/pos/invoices -H 'Content-Type: application/json' \
  -d "{\"customer_id\":$CID,\"vehicle_id\":$VID,\"items\":[{\"item_type\":\"product\",\"product_id\":$PID,\"quantity\":2,\"unit_price_paisa\":25000,\"discount_paisa\":1000}],\"payments\":[{\"amount_paisa\":49000,\"method\":\"cash\"}]}")
INVID=$(echo "$INV" | j "['id']")
INUM=$(echo "$INV" | j "['invoice_number']")
echo "invoice $INUM total=$(echo "$INV" | j "['total_paisa']") (expect 49000)"
[ "$(echo "$INV" | j "['total_paisa']")" = "49000" ] || { echo "FAIL total"; exit 1; }
[ "$(echo "$INV" | j "['status']")" = "paid" ] || { echo "FAIL status"; exit 1; }
STOCK3=$(curl -s -H "$AUTH" "$BASE/api/products?q=NGK" | j "['items'][0]['quantity_on_hand']")
echo "stock after sale of 2: $STOCK3 (expect 7)"
[ "$STOCK3" = "7" ] || { echo "FAIL stock after sale"; exit 1; }

echo "== 9. Job invoice (workflow B) =="
JINV=$(curl -s -H "$AUTH" -X POST $BASE/api/jobs/$JOBID/invoice -H 'Content-Type: application/json' -d '{}')
echo "job invoice total=$(echo "$JINV" | j "['total_paisa']") (expect 105000)"
[ "$(echo "$JINV" | j "['total_paisa']")" = "105000" ] || { echo "FAIL job invoice"; exit 1; }
STOCK4=$(curl -s -H "$AUTH" "$BASE/api/products?q=NGK" | j "['items'][0]['quantity_on_hand']")
echo "stock after job invoice (must not double-deduct): $STOCK4 (expect 7)"
[ "$STOCK4" = "7" ] || { echo "FAIL double deduction"; exit 1; }

echo "== 10. Credit sale + partial payment + repayment =="
CINV=$(curl -s -H "$AUTH" -X POST $BASE/api/pos/invoices -H 'Content-Type: application/json' \
  -d "{\"customer_id\":$CID,\"items\":[{\"item_type\":\"product\",\"product_id\":$PID,\"quantity\":1,\"unit_price_paisa\":25000}],\"payments\":[{\"amount_paisa\":10000,\"method\":\"cash\"}],\"is_credit\":true}")
echo "credit invoice status=$(echo "$CINV" | j "['status']") balance=$(echo "$CINV" | j "['balance_paisa']")"
[ "$(echo "$CINV" | j "['status']")" = "partial" ] || { echo "FAIL credit"; exit 1; }
CINVID=$(echo "$CINV" | j "['id']")
curl -s -H "$AUTH" -X POST $BASE/api/invoices/$CINVID/payments -H 'Content-Type: application/json' \
  -d '{"amount_paisa":15000,"method":"cash"}' > /dev/null
BAL=$(curl -s -H "$AUTH" $BASE/api/customers/$CID | j "['balance_paisa']")
echo "customer outstanding after repayments: $BAL"

echo "== 11. Shift reconciliation (workflow F) =="
SHIFT=$(curl -s -H "$AUTH" -X POST $BASE/api/shifts/open -H 'Content-Type: application/json' \
  -d '{"opening_cash_paisa":500000}')
SHIFTID=$(echo "$SHIFT" | j "['id']")
echo "shift opened: $SHIFTID"
# create a cash sale under this shift
curl -s -H "$AUTH" -X POST $BASE/api/pos/invoices -H 'Content-Type: application/json' \
  -d "{\"items\":[{\"item_type\":\"product\",\"product_id\":$PID,\"quantity\":1,\"unit_price_paisa\":25000}],\"payments\":[{\"amount_paisa\":25000,\"method\":\"cash\"}]}" > /dev/null
EXP=$(curl -s -H "$AUTH" $BASE/api/shifts/current | j "['expected_cash_paisa']")
echo "expected cash: $EXP (expect 500000+10000+15000+25000=550000 minus... check)"
curl -s -H "$AUTH" -X POST $BASE/api/shifts/$SHIFTID/close -H 'Content-Type: application/json' \
  -d "{\"counted_cash_paisa\":$EXP}" | j "['status']"

echo "== 12. Return workflow (workflow D) =="
RET=$(curl -s -H "$AUTH" -X POST $BASE/api/invoices/returns -H 'Content-Type: application/json' \
  -d "{\"invoice_id\":$INVID,\"reason\":\"defective\",\"restock_action\":\"restock\",\"refund_method\":\"cash\",\"items\":[{\"invoice_item_id\":$(echo "$INV" | j "['items'][0]['id']"),\"quantity\":1}]}")
RETID=$(echo "$RET" | j "['id']")
curl -s -H "$AUTH" -X POST $BASE/api/invoices/returns/$RETID/decide -H 'Content-Type: application/json' \
  -d '{"status":"approved"}' > /dev/null
STOCK5=$(curl -s -H "$AUTH" "$BASE/api/products?q=NGK" | j "['items'][0]['quantity_on_hand']")
echo "stock after approved return of 1: $STOCK5 (expect 8)"

echo "== 13. Void workflow =="
VOID=$(curl -s -H "$AUTH" -X POST $BASE/api/invoices/$INVID/void -H 'Content-Type: application/json' \
  -d '{"reason":"customer requested"}')
echo "voided status=$(echo "$VOID" | j "['status']")"
STOCK6=$(curl -s -H "$AUTH" "$BASE/api/products?q=NGK" | j "['items'][0]['quantity_on_hand']")
echo "stock after void (restored 2): $STOCK6"

echo "== 14. Dashboard =="
curl -s -H "$AUTH" "$BASE/api/reports/dashboard" | j "['sales']['revenue_paisa']"

echo "== 15. Backup + restore =="
BK=$(curl -s -H "$AUTH" -X POST $BASE/api/backups | j "['filename']")
echo "backup: $BK"
curl -s -H "$AUTH" -X POST $BASE/api/backups/validate?filename=$BK | j "['ok']"

echo "== 16. Warranty Claims + Returns List (v1.2.1) =="
RLIST=$(curl -s -H "$AUTH" "$BASE/api/invoices/returns?page_size=20" | j "['total']")
echo "returns count: $RLIST"
CLMID=$(curl -s -H "$AUTH" -X POST $BASE/api/claims -H 'Content-Type: application/json' \
  -d "{\"customer_id\":$CID,\"vehicle_id\":$VID,\"product_id\":$PID,\"item_type\":\"product\",\"description\":\"Electrode wear under warranty\",\"status\":\"open\"}" | j "['id']")
curl -s -H "$AUTH" -X PUT $BASE/api/claims/$CLMID -H 'Content-Type: application/json' \
  -d '{"status":"resolved","resolution":"replaced"}' | j "['status']"
curl -s -H "$AUTH" -X DELETE $BASE/api/claims/$CLMID | j "['ok']"

echo "== 17. PWA Manifest, Icons & Service Worker (v1.2.2) =="
VER=$(curl -s "$BASE/api/health" | j "['version']")
[ "$VER" = "1.2.2" ] || { echo "FAIL: health version $VER"; exit 1; }
MNAME=$(curl -s "$BASE/manifest.webmanifest" | j "['name']")
[ "$MNAME" = "Auto Workshop Management POS" ] || { echo "FAIL: manifest $MNAME"; exit 1; }
SW_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/sw.js")
[ "$SW_CODE" = "200" ] || { echo "FAIL: sw.js $SW_CODE"; exit 1; }
IC_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/assets/icons/icon-512.png")
[ "$IC_CODE" = "200" ] || { echo "FAIL: icon-512.png $IC_CODE"; exit 1; }
echo "ALL SMOKE TESTS PASSED (v$VER)"
