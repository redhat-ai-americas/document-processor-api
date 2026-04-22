#!/bin/bash

INPUT_FILE="$1"

if [ -z "$INPUT_FILE" ]; then
  echo "Error: input file argument is required" >&2
  echo "Usage: $0 <file>" >&2
  exit 1
fi

export NAMESPACE=docling
export DEPLOYMENT=docling-serve
export URL=$(oc get routes $DEPLOYMENT -o jsonpath='{.spec.host}' -n $NAMESPACE)

#echo "Docling Serve API Endpoint: $URL"
#echo "Document Path to Convert: $TEST_FILE"

curl -s -X 'POST' \
  "https://$URL/v1/convert/file" \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'from_formats=pdf' \
  -F 'from_formats=docx' \
  -F 'force_ocr=false' \
  -F 'image_export_mode=embedded' \
  -F 'ocr_lang=en' \
  -F 'table_mode=fast' \
  -F "files=@$INPUT_FILE;type=application/pdf" \
  -F 'abort_on_error=false' \
  -F 'to_formats=md' \
  -F 'do_ocr=true' \
  | jq -r .document.md_content


