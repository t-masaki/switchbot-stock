# TDSE・日経225 → SwitchBot Daily Station

AWS Lambda（Python 3.13）でYahoo Finance互換の `7046.T` / `^N225` を取得し、SwitchBot OpenAPI v1.1 の `customPutComponent` に現在値・前日比・騰落率を送ります。初回のSSM登録後、`terraform init` → `terraform apply` でAWSリソースを作成できます。

表示例（数値は架空）：

```text
TDSE 1234円 +34(+2.83%) | 日経225 48321 -180(-0.37%) | 最古10/02 15:20 JST 遅延
```

日経225は指数値なので円単位を付けません。各価格の直後が前日比、括弧内が騰落率です。「最古」は2銘柄の相場時刻のうち古い方で、送信時刻ではありません。価格・前日比は小数第2位まで表示し、末尾のゼロを省略します。1つのカスタムテキストコンポーネントに両銘柄をまとめます。

ユーザー提供の「カスタムコンポーネント API ガイド」に基づき、最大100文字として送信前に検査します。100文字超過は自動省略に任せずエラーにし、既存表示を残します。従来のcustomPageの300バイト制限は使用しません。APIの改行仕様は提供ガイドに明記されていないため、表示は1行としています。コンポーネントの大きさ・文字サイズによる見切れは実機で調整してください。

## カスタムコンポーネントの準備・既存環境の更新

1. SwitchBotエディタで「カスタムテキスト」を追加します。
2. 画面上部のテンプレートIDと対象コンポーネントIDを確認します。
3. **テンプレートを対象デバイスへ公開してください。未公開ではAPI更新が反映されません。**
4. `terraform/terraform.tfvars` に以下を追加します。提供された値を設定例にしていますが、ご自身のエディタの値と照合してください。

```hcl
template_id = 5874
component_id = 801332647
```

既存環境は更新版ソースを同じプロジェクトへ配置し、既存のTerraform state・設定・ロックファイルを維持した状態で `terraform init` → `terraform plan` → `terraform apply` を実行します。新しい空の作業ディレクトリから、既存stateに接続せずapplyしないでください。既存のSSM値はそのまま使えます。

IDはTerraformの必須数値変数として設定し、Lambda環境変数 `TEMPLATE_ID` / `COMPONENT_ID` に渡します。これらのIDはstateに入ります。Token・Secret・Device IDは引き続きSSMで扱います。API呼出しは以下です（DEVICE_IDはSSMから読込み）。

```text
POST https://api.switch-bot.com/v1.1/devices/{DEVICE_ID}/commands
```

```json
{
  "commandType": "command",
  "command": "customPutComponent",
  "parameter": {
    "templateID": 5874,
    "componentID": 801332647,
    "text": "TDSEと日経225の表示テキスト"
  }
}
```

提供ガイド冒頭の `/devices//commands` はIDが空ですが、同ガイドのコード例に従いDevice IDを埋め込みます。`parameter` はJSONオブジェクト、2つのIDはJSON数値として送信します。

## 構成

```text
EventBridge Scheduler（Asia/Tokyo、平日10分ごと）
  → Lambda → market_data.py → Yahoo Finance chart endpoint
           → SSM SecureString（実行時に復号）
           → SwitchBot v1.1 customPutComponent
```

- `lambda/market_data.py`：市場データ取得と共通の `Quote`。他社APIに替える場合は `get_quote(symbol)` を同じ戻り値で実装します。
- `lambda/lambda_function.py`：時刻制御・表示整形・SSM読込み。
- `lambda/switchbot.py`：署名、デバイス一覧、カスタムコンポーネント送信。
- `lambda/http_client.py`：タイムアウト付きHTTPS。エラーに認証ヘッダー、Device ID入りURL、応答本文を出しません。
- `terraform/`：IAM、Lambda、ログ、Scheduler、ZIP生成。
- `scripts/setup_credentials.py`：秘密値を非表示入力し、SSMに直接登録。
- `tests/test_stock.py`：外部通信しない単体テスト。

## 実行時刻とデータの制約

Schedulerを2本に分け、平日09:00〜14:50の10分刻みと15:00・15:10・15:20・15:30に起動します。15:40以降は起動しません。Lambda側は **11:30以上12:30未満** をスキップするため、昼の最終送信は11:20、再開は12:30です。Schedulerには秒単位の保証がないため、15:30台を許可します。1平日40起動、通常34回の送信です。

Yahooのエンドポイントは非公式で、可用性・更新頻度・遅延時間・継続利用を保証できません。403/429等の場合は関数を失敗させ、既存表示を残します。両方のデータが揃った場合のみ送信します。前日比は `regularMarketPrice - chartPreviousClose`、騰落率はこれを前営業日終値で割って100倍します。`range=1d` のメタデータを使用し、価格や前営業日終値が欠けた場合に別の基準値へ推測で代替しません。

JPXの祝日カレンダーは実装していません。平日の祝日にも起動しますが、いずれかの相場日付が当日のJST日付でなければ送信をスキップします。同日内の古いデータは2銘柄の最古時刻付きで表示します。この判定は完全な休場判定ではありません。引け後の追加取得もないため、15:30に取得した値が公式終値とは限りません。遅延した終値を確実に表示する場合は、後刻の取得スケジュール・時刻制御の追加が必要です。

## 1. 必要なもの

- AWSアカウント、認証済みAWS CLI v2、Terraform 1.5以上2.0未満、Python 3.10以上。
- AWS操作権限：Lambda、IAMロール/ポリシーとPassRole、Scheduler、CloudWatch Logsの作成・更新・削除。セットアップ用に対象パスへの `ssm:PutParameter`。
- インターネットアクセス可能なローカル環境。LambdaはVPCに接続しない構成です。
- SwitchBotアプリで設定済みのDaily Stationと、利用可能なクラウド接続。

AWS認証はプロファイルやSSOを使用してください。AWSアクセスキーをこのプロジェクトに書き込まないでください。

```sh
aws sso login --profile YOUR_PROFILE
export AWS_PROFILE=YOUR_PROFILE
export AWS_DEFAULT_REGION=ap-northeast-1
aws sts get-caller-identity
```

以降は展開した `switchbot-stock` フォルダーで操作します。

## 2. SwitchBot Token / SecretとDevice ID

SwitchBotアプリのプロフィール → 設定 → バージョン情報（About）へ進み、アプリバージョンを10回タップして「開発者向けオプション」を表示し、TokenとSecretを取得します。アプリのバージョン・日本語表記によって「基本データ」など経路が異なります。取得した値はチャットやリポジトリに貼り付けないでください。

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r lambda/requirements.txt
python -B scripts/setup_credentials.py --region ap-northeast-1 --prefix /switchbot-stock
```

スクリプトはToken / Secretを非表示入力で受け取り、署名付き `GET /v1.1/devices` を実行します。表示されたID・種別・名前からDaily Stationを確認し、Device IDを入力します。公式資料には `WeatherStation` / `Weather Station` / `WoIOSensor` の表記があるため、名前と実際の機器を照合してください。デバイス一覧には個人が付けた名前も含まれるため、端末出力をそのまま共有しないでください。

次の3つをAWS管理キー `alias/aws/ssm` によるSecureStringとして登録します。

```text
/switchbot-stock/token
/switchbot-stock/secret
/switchbot-stock/device-id
```

既存値の更新時のみ `--overwrite` を追加します。3件の書込みはトランザクションではありません。途中失敗時は権限・リージョンを確認し、同じ入力で `--overwrite` を付けて再実行してください。

TerraformはSSMの値を作成・参照・出力しません。秘密値の変数やSSMデータソースもありません。この設計により、秘密値をTerraform stateへ取り込みません。Lambda環境変数にはパスだけを設定し、実行ロールの `ssm:GetParameters` は3つのARNに限定します。AWS管理キーを使うため独自のKMSポリシーは不要です。独自KMSキーに変更する場合は、実行ロールの `kms:Decrypt` とキー側ポリシーを追加してください。state自体にはAWSリソース情報が含まれるので適切に保管してください。

## 3. デプロイ

```sh
cd terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform fmt
terraform validate
terraform plan
terraform apply
```

デフォルトリージョンは東京です。名前、リージョン、`ssm_prefix` を変更した場合は、セットアップ時のパス・リージョンも一致させてください。ZIPはTerraformのarchiveプロバイダーが自動生成します。Lambdaは標準ライブラリと実行環境内蔵boto3を利用するため、デプロイ用のpipインストールは不要です。`requirements.txt` のboto3はローカル設定スクリプト用です。SDKの完全なバージョン固定が必要な運用では依存物をZIPへ同梱する方式に変更してください。

`terraform init` で生成される `.terraform.lock.hcl` は、継続管理するリポジトリにコミットしてください。AWS認証・SSM登録前でもリソースの作成自体はできますが、送信時にSSMが未登録なら失敗します。登録前に作成する場合は `schedule_enabled = false` にしてください。

## 4. テスト

プロジェクトルートで、通信なしのテスト：

```sh
python3 -B -m unittest discover -s tests -v
```

デプロイ後、`terraform` フォルダーで市場データだけ取得するテスト（SwitchBotに送信せず、SSMも読みません）：

```sh
aws lambda invoke --region ap-northeast-1 \
  --function-name "$(terraform output -raw function_name)" \
  --cli-binary-format raw-in-base64-out \
  --payload '{"force":true,"dry_run":true}' response.json
cat response.json
```

`force` は時刻・同日データ判定を迂回する手動テスト用です。休場中は過去のデータを返す場合があります。通常のScheduler入力は空オブジェクトであり、迂回しません。

実機への送信テスト：

```sh
aws lambda invoke --region ap-northeast-1 \
  --function-name "$(terraform output -raw function_name)" \
  --cli-binary-format raw-in-base64-out \
  --payload '{"force":true}' response.json
cat response.json
```

`aws lambda invoke` のHTTP 200だけでは成功とは限りません。CLI出力に `FunctionError` がなく、応答の `status` が `sent` であることを確認してください。`sent` はAPI受付成功であり、実機反映保証ではありません。Daily Stationで公開済みテンプレートの対象コンポーネントを確認します。反映しない場合はテンプレートの公開状態、2つのID、デバイスのオンライン状態を確認し、E-ink更新まで数秒待ってください。

```sh
aws logs tail /aws/lambda/switchbot-stock --region ap-northeast-1 --since 1h
```

API失敗はLambdaエラーとしてCloudWatchに記録されます。自動リトライはScheduler・Lambdaとも無効です。次の10分更新を待ちます。エラー通知用SNS/Alarm、DLQはこの最小構成にはありません。CloudWatchのLambda Errors・Scheduler TargetErrorCountなどを運用時に確認してください。AWS利用料金はアカウント・無料枠・使用量に依存します。

## 5. 一時停止・削除

一時停止：

```sh
terraform apply -var='schedule_enabled=false'
```

AWSリソース削除（`terraform` フォルダー）：

```sh
terraform destroy
```

SSMはTerraform管理外なので残ります。不要になった場合のみ別途削除します（独自パスを使った場合は変更）。

```sh
aws ssm delete-parameters --region ap-northeast-1 \
  --names /switchbot-stock/token /switchbot-stock/secret /switchbot-stock/device-id
```

`destroy` ではDaily Station上の既存テキストは消えません。必要に応じてアプリで別ページに切り替えてください。

## 検証結果と未確認事項

作成環境では、外部通信をモックした単体テスト13件が成功しました。Pythonソースの構文も検証済みです。Terraform実行ファイルが環境になく、配布サイトへの名前解決も失敗したため `init / validate / plan` は未実施です。上記の手順で利用環境から実行してください。AWSへの実デプロイ、Yahooのライブ応答、SSM読込み、実機表示は未確認です。

## 参照仕様

- [SwitchBot OpenAPI v1.1：認証・デバイス一覧](https://github.com/OpenWonderLabs/SwitchBotAPI)
- カスタムコンポーネント部分：ユーザー提供「カスタムコンポーネント API ガイド」（customPutComponent、100文字上限、公開済みテンプレートが必要）。公開URLは未提供。
- [EventBridge Schedulerのcron・タイムゾーン・精度](https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html)

SwitchBot OpenAPIの利用条件を確認した上で個人利用してください。Yahooデータ取得は正式なサポート付き市場データAPIではありません。継続運用に保証が必要なら `market_data.py` を契約済み提供元へ交換してください。
