export interface TransactionRow {
  id: string;
  source_txn_id: string;
  account_id: string;
  account_name: string | null;
  customer_id: string;
  amount: number | null;
  counterparty: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  date: string | null;
}

export interface CustomerSummary {
  customer_id: string;
  first_name: string;
  last_name: string;
  city: string | null;
  state: string | null;
}

export interface AccountDetail {
  account_id: string;
  name: string | null;
  bank: string | null;
  type: string | null;
  date_opened: string | null;
}

export interface CustomerDetail {
  customer_id: string;
  first_name: string;
  last_name: string;
  address_line: string | null;
  city: string | null;
  state: string | null;
  zip: string | null;
  accounts: AccountDetail[];
}

export interface AccountResponse {
  account_id: string;
  name: string | null;
  bank: string | null;
  type: string | null;
  date_opened: string | null;
  customer_id: string;
}

export interface UploadSummary {
  id: string;
  filename: string;
  status: string;
  total_rows: number | null;
  accepted_count: number | null;
  failed_count: number;
  uploaded_at: string | null;
  eval_file: string | null;
  pending_sar_count: number;
}

export interface PendingSAR {
  sar_id: string;
  transaction_id: string;
  upload_id: string;
  source_txn_id: string | null;
  account_id: string | null;
  customer_id: string | null;
  customer_first_name: string | null;
  customer_last_name: string | null;
  amount: number | null;
  counterparty: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  date: string | null;
  flag_details: Record<string, string> | null;
  risk_level: string | null;
  triage_reasoning: string | null;
  enrichment: Record<string, unknown> | null;
  rule_name: string | null;
  rule_description: string | null;
  sar_content: string;
  sar_status: string;
  created_at: string | null;
}

export interface PaginatedResponse<T> {
  page: number;
  per_page: number;
  total: number;
  items: T[];
}

export interface RuleResponse {
  id: string;
  name: string;
  description: string | null;
  type: string;
  status: string;
  rules_json: Record<string, unknown>[];
}

export interface RuleCreate {
  name: string;
  description?: string | null;
  type?: string;
  status?: string;
  rules_json: Record<string, unknown>[];
}

export interface GenerateStep {
  type: "upload" | "stage1" | "stage2" | "synthetic";
  count: number;
  bad_rate: number;
}

export interface GenerateRequest {
  steps: GenerateStep[];
  shuffle: boolean;
  date: string | null;
}

export interface GenerateResponse {
  download_url: string;
  filename: string;
  eval_url: string | null;
}

export interface CsvPreview {
  fieldnames: string[];
  rows: Record<string, string>[];
}

export interface EvalEntry {
  source_txn_id: string;
  scenario: string;
  expected_escalate: boolean;
  ground_truth: string;
  reason_hint: string;
}

export interface PatternMetrics {
  pattern: string;
  total: number;
  flagged: number;
  precision: number;
  recall: number;
  f1: number;
}

export interface HallucinationResult {
  sar_id: string;
  transaction_id: string;
  hallucinated_facts: string[];
  passed: boolean;
}

export interface CompletenessResult {
  sar_id: string;
  transaction_id: string;
  covered_rules: string[];
  missed_rules: string[];
  score: number;
}

export interface EvalReport {
  upload_id: string;
  total_transactions: number;
  total_anomalous: number;
  total_flagged: number;
  pattern_metrics: PatternMetrics[];
  hallucination_results: HallucinationResult[];
  completeness_results: CompletenessResult[];
  overall_precision: number;
  overall_recall: number;
  overall_f1: number;
  hallucination_free_rate: number;
  avg_completeness: number;
}
