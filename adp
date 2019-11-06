#!/usr/bin/env bash
STATE=FL
PAY_RATE=${PAY_RATE:-70}
HOURS_IN_MONTH=${1:-160}
PAY_FREQUENCY=MONTHLY

month=$(date +%m | sed -e 's/^0\+//g')
day=$(date +%d | sed -e 's/^0\+//g')
#((day >= 15)) && ((month++))
year=$(date +%Y)
#((day >= 15)) && ((month == 12)) && ((year++))
check_date=$(($(date -d "${year}-${month}-${day}" +%S) * 1000))
gross_pay=$((HOURS_IN_MONTH * PAY_RATE))

payload=$(
    cat << EOF
{
  "checkDate": ${check_date},
  "state": "${STATE}",
  "rates": [{
    "payRate": "${PAY_RATE}",
    "hours": "${HOURS_IN_MONTH}"
  }],
  "grossPay": "${gross_pay}.00",
  "grossPayType": "PAY_PER_PERIOD",
  "grossPayYTD": "0",
  "payFrequency": "${PAY_FREQUENCY}",
  "exemptFederal": "false",
  "exemptFica": "false",
  "exemptMedicare": "false",
  "federalFilingStatusType": "SINGLE",
  "federalAllowances": "0",
  "additionalFederalWithholding": "0",
  "roundFederalWithholding": "false",
  "print": {
    "id": "",
    "employeeName": "",
    "employeeAddressLine1": "",
    "employeeAddressLine2": "",
    "employeeAddressLine3": "",
    "checkNumber": "",
    "checkNumberOnCheck": "false",
    "checkDate": 1484802000000,
    "remarks": "",
    "companyNameOnCheck": "false",
    "companyName": "",
    "companyAddressLine1": "",
    "companyAddressLine2": "",
    "companyAddressLine3": ""
  },
  "otherIncome": [],
  "payCodes": [],
  "stockOptions": [],
  "stateInfo": {
    "parms": [{
      "name": "TOTALALLOWANCES",
      "value": "0"
    }, {
      "name": "additionalStateWithholding",
      "value": "0"
    }, {
      "name": "SPOUSEBLINDNESS",
      "value": "false"
    }, {
      "name": "stateExemption",
      "value": "false"
    }, {
      "name": "PERSONALBLINDNESS",
      "value": "false"
    }, {
      "name": "HEADOFHOUSEHOLD",
      "value": "false"
    }, {
      "name": "FULLTIMESTUDENT",
      "value": "false"
    }]
  },
  "voluntaryDeductions": [],
  "presetDeductions": []
}
EOF
)
# Find the API key by looking at requests on this page
# http://www.symmetry.com/try-it-for-free/calculators
out=$(curl -q -s 'https://calculators.symmetry.com/api/calculators/hourly?report=none' \
    -H 'origin: https://www.adp.com' -H 'accept-encoding: gzip, deflate, br' \
    -H 'accept-language: en-GB,en-US;q=0.8,en;q=0.6' \
    -H 'pcc-api-key: RnFqNFA0NVlRTExJUkpabmc4RHErUT09' \
    -H 'pragma: no-cache' \
    -H 'content-type: application/json' \
    -H 'accept: application/json, text/javascript, */*; q=0.01' \
    -H 'cache-control: no-cache' \
    -H 'authority: calculators.symmetry.com' \
    -H 'referer: https://www.adp.com/tools-and-resources/calculators-and-tools/payroll-calculators/hourly-paycheck-calculator.aspx' \
    -H 'dnt: 1' \
    --data-binary "$payload" \
    --compressed)
federal=$(jq -S .content.federal <<< "$out")
fica=$(jq -S .content.fica <<< "$out")
state=$(jq -S .content.state <<< "$out")
medicare=$(jq -S .content.medicare <<< "$out")
net=$(jq -S .content.netPay <<< "$out")
printf "Gross     \033[1;32m%8.2f\033[0m\n" "${gross_pay}.00"
printf "Federal   \033[1;31m%8.2f\033[0m\n" "$federal"
printf "FICA      \033[1;31m%8.2f\033[0m\n" "$fica"
printf "State     \033[1;31m%8.2f\033[0m\n" "$state"
printf "Medicare  \033[1;31m%8.2f\033[0m\n" "$medicare"
echo "------------------"
printf "Net       \033[1;32m%8.2f\033[0m\n" "$net"
echo
echo "------------------"
printf "Fuckery   \033[1;31m%8.2f\n" "$(dc <<< "$gross_pay $net - p")"
# echo
# jq -r ._links.self.href <<< "$out"
