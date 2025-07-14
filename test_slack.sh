#!/bin/bash

# Slack Webhook テストスクリプト
# 使い方: ./test_slack.sh "YOUR_WEBHOOK_URL"

WEBHOOK_URL=$1

if [ -z "$WEBHOOK_URL" ]; then
    echo "使い方: ./test_slack.sh \"https://hooks.slack.com/services/...\""
    exit 1
fi

# テストメッセージを送信
curl -X POST -H 'Content-type: application/json' \
    --data '{
        "text": "freee自動仕訳システムのテストメッセージです :white_check_mark:",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Slack連携テスト成功！* :tada:\nfreee自動仕訳システムの通知が正常に設定されました。"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": "*システム:*\nfreee × Claude"
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*実行時刻:*\n毎週月曜 AM 9:00"
                    }
                ]
            }
        ]
    }' \
    "$WEBHOOK_URL"

echo ""
echo "テストメッセージを送信しました。Slackを確認してください。"