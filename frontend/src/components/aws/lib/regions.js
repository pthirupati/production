// All AWS regions with display names and geography grouping. Each region carries
// its 3 default AZ suffixes used for seeding/launch wizards.
export const AWS_REGIONS = [
  { code: 'us-east-1', name: 'US East (N. Virginia)', geo: 'North America', flag: '🇺🇸' },
  { code: 'us-east-2', name: 'US East (Ohio)', geo: 'North America', flag: '🇺🇸' },
  { code: 'us-west-1', name: 'US West (N. California)', geo: 'North America', flag: '🇺🇸' },
  { code: 'us-west-2', name: 'US West (Oregon)', geo: 'North America', flag: '🇺🇸' },
  { code: 'ca-central-1', name: 'Canada (Central)', geo: 'North America', flag: '🇨🇦' },
  { code: 'ca-west-1', name: 'Canada West (Calgary)', geo: 'North America', flag: '🇨🇦' },
  { code: 'sa-east-1', name: 'South America (São Paulo)', geo: 'South America', flag: '🇧🇷' },
  { code: 'eu-west-1', name: 'Europe (Ireland)', geo: 'Europe', flag: '🇮🇪' },
  { code: 'eu-west-2', name: 'Europe (London)', geo: 'Europe', flag: '🇬🇧' },
  { code: 'eu-west-3', name: 'Europe (Paris)', geo: 'Europe', flag: '🇫🇷' },
  { code: 'eu-central-1', name: 'Europe (Frankfurt)', geo: 'Europe', flag: '🇩🇪' },
  { code: 'eu-central-2', name: 'Europe (Zurich)', geo: 'Europe', flag: '🇨🇭' },
  { code: 'eu-north-1', name: 'Europe (Stockholm)', geo: 'Europe', flag: '🇸🇪' },
  { code: 'eu-south-1', name: 'Europe (Milan)', geo: 'Europe', flag: '🇮🇹' },
  { code: 'eu-south-2', name: 'Europe (Spain)', geo: 'Europe', flag: '🇪🇸' },
  { code: 'ap-northeast-1', name: 'Asia Pacific (Tokyo)', geo: 'Asia Pacific', flag: '🇯🇵' },
  { code: 'ap-northeast-2', name: 'Asia Pacific (Seoul)', geo: 'Asia Pacific', flag: '🇰🇷' },
  { code: 'ap-northeast-3', name: 'Asia Pacific (Osaka)', geo: 'Asia Pacific', flag: '🇯🇵' },
  { code: 'ap-southeast-1', name: 'Asia Pacific (Singapore)', geo: 'Asia Pacific', flag: '🇸🇬' },
  { code: 'ap-southeast-2', name: 'Asia Pacific (Sydney)', geo: 'Asia Pacific', flag: '🇦🇺' },
  { code: 'ap-southeast-3', name: 'Asia Pacific (Jakarta)', geo: 'Asia Pacific', flag: '🇮🇩' },
  { code: 'ap-southeast-4', name: 'Asia Pacific (Melbourne)', geo: 'Asia Pacific', flag: '🇦🇺' },
  { code: 'ap-southeast-5', name: 'Asia Pacific (Malaysia)', geo: 'Asia Pacific', flag: '🇲🇾' },
  { code: 'ap-southeast-7', name: 'Asia Pacific (Thailand)', geo: 'Asia Pacific', flag: '🇹🇭' },
  { code: 'ap-south-1', name: 'Asia Pacific (Mumbai)', geo: 'Asia Pacific', flag: '🇮🇳' },
  { code: 'ap-south-2', name: 'Asia Pacific (Hyderabad)', geo: 'Asia Pacific', flag: '🇮🇳' },
  { code: 'ap-east-1', name: 'Asia Pacific (Hong Kong)', geo: 'Asia Pacific', flag: '🇭🇰' },
  { code: 'me-south-1', name: 'Middle East (Bahrain)', geo: 'Middle East', flag: '🇧🇭' },
  { code: 'me-central-1', name: 'Middle East (UAE)', geo: 'Middle East', flag: '🇦🇪' },
  { code: 'il-central-1', name: 'Israel (Tel Aviv)', geo: 'Middle East', flag: '🇮🇱' },
  { code: 'af-south-1', name: 'Africa (Cape Town)', geo: 'Africa', flag: '🇿🇦' },
  { code: 'us-gov-east-1', name: 'AWS GovCloud (US-East)', geo: 'GovCloud', flag: '🇺🇸' },
  { code: 'us-gov-west-1', name: 'AWS GovCloud (US-West)', geo: 'GovCloud', flag: '🇺🇸' },
]

export const REGION_GEO_ORDER = [
  'North America', 'South America', 'Europe', 'Asia Pacific', 'Middle East', 'Africa', 'GovCloud',
]

export function regionName(code) {
  return AWS_REGIONS.find((r) => r.code === code)?.name || code
}

// 3 AZs per region (a/b/c) — enough for the launch wizard + subnet seeding.
export function regionAZs(code) {
  return ['a', 'b', 'c'].map((s) => `${code}${s}`)
}
