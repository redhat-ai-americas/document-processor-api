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

POLL_INTERVAL=5

# Submit the file for async conversion
SUBMIT_RESPONSE=$(curl -s -X 'POST' \
  "https://$URL/v1/convert/file/async" \
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
  -F 'do_ocr=true')

TASK_ID=$(echo "$SUBMIT_RESPONSE" | jq -r '.task_id')

if [ -z "$TASK_ID" ] || [ "$TASK_ID" = "null" ]; then
  echo "Error: failed to get task_id from submission response" >&2
  echo "$SUBMIT_RESPONSE" >&2
  exit 1
fi

echo "Task submitted: $TASK_ID" >&2

# Poll until the task reaches a terminal state
while true; do
  POLL_RESPONSE=$(curl -s "https://$URL/v1/status/poll/$TASK_ID")
  TASK_STATUS=$(echo "$POLL_RESPONSE" | jq -r '.task_status')

  echo "Status: $TASK_STATUS" >&2

  if [ "$TASK_STATUS" = "success" ]; then
    break
  elif [ "$TASK_STATUS" = "failure" ]; then
    echo "Error: conversion failed" >&2
    echo "$POLL_RESPONSE" >&2
    exit 1
  fi

  sleep $POLL_INTERVAL
done

# Fetch and print the result
curl -s "https://$URL/v1/result/$TASK_ID" | jq . # -r .document.md_content
