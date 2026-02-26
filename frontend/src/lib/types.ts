export type ListingType = "전세" | "월세" | "매매";
export type PropertyType = "아파트" | "연립다세대" | "단독다가구" | "오피스텔";
export type SuspiciousCategory = "EXAGGERATION" | "MISLEADING" | "PRICE_BAIT" | "OMISSION" | "NORMAL";
export type Severity = "LOW" | "MEDIUM" | "HIGH";
export type RiskGrade = "안전" | "주의" | "경고" | "위험";
export type PriceAssessment = "적정" | "저가의심" | "고가의심";

export interface RegistryInput {
  owner?: string | null;
  mortgage?: number | null;
  seizure: boolean;
  trust: boolean;
  raw_text?: string | null;
}

export interface ListingAnalysisRequest {
  listing_text: string;
  listing_type: ListingType;
  property_type: PropertyType;
  address: string;
  building_name?: string;
  deposit: number;
  monthly_rent?: number | null;
  area_sqm: number;
  registry?: RegistryInput | null;
}

export interface SuspiciousExpression {
  text: string;
  category: SuspiciousCategory;
  severity: Severity;
  reason: string;
}

export interface TextAnalysisResult {
  suspicious_expressions: SuspiciousExpression[];
  analyzed: boolean;
}

export interface ExtractedInfo {
  price: string | null;
  area: string | null;
  floor: string | null;
  location_claims: string[];
  facilities: string[];
}

export interface RecentTrade {
  price: number;
  area_sqm: number;
  year: number;
  month: number;
  day: number;
  dong: string;
  name: string;
  floor: number;
  trade_type: string;
}

export interface MarketComparison {
  avg_market_price: number | null;
  avg_sale_price: number | null;
  deviation_rate: number | null;
  assessment: PriceAssessment | null;
  data_count: number;
  data_scope: string;
  recent_trades: RecentTrade[];
  monthly_trends: MonthlyTrend[];
}

export interface RegistryAnalysis {
  owner: string | null;
  mortgage: number;
  seizure: boolean;
  trust: boolean;
}

export interface InsuranceCheck {
  eligible: boolean;
  verdict: string;
  reasons: string[];
  tips: string[];
}

export interface MonthlyTrend {
  month: string;
  avg_trade: number | null;
  avg_rent: number | null;
  trade_count: number;
  rent_count: number;
}

export interface JeonseRisk {
  jeonse_rate: number | null;
  total_burden_ratio: number | null;
  auction_recovery_risk: number | null;
  estimated_actual_debt: number | null;
  risk_score: number;
  risk_grade: RiskGrade;
  risk_factors: string[];
  registry_analysis: RegistryAnalysis | null;
  checklist: string[];
  insurance_check: InsuranceCheck | null;
}

export interface AiReportSection {
  title: string;
  icon: string;
  content: string;
  verdict: string;
}

export interface LocationClaim {
  claim: string;
  category: string;
  verified: boolean;
  nearest_name: string;
  actual_distance_m: number;
  actual_walk_min: number;
  claimed_walk_min: number | null;
  verdict: string;
}

export interface LocationVerification {
  claims: LocationClaim[];
  verified_count: number;
  exaggerated_count: number;
}

export interface NearbyFacility {
  name: string;
  category: string;
  distance_m: number;
  walk_min: number;
}

export interface NearbyFacilities {
  subway: NearbyFacility[];
  school: NearbyFacility[];
  mart: NearbyFacility[];
  hospital: NearbyFacility[];
  park: NearbyFacility[];
  convenience: NearbyFacility[];
  cafe: NearbyFacility[];
  bank: NearbyFacility[];
}

export interface AnalysisReport {
  listing_type: ListingType;
  reliability_score: number;
  reliability_grade: RiskGrade;
  evaluation: string;
  ai_report: AiReportSection[];
  text_analysis: TextAnalysisResult;
  extracted_info: ExtractedInfo;
  market_comparison: MarketComparison;
  location_verification: LocationVerification | null;
  nearby_facilities: NearbyFacilities | null;
  jeonse_risk: JeonseRisk | null;
}
