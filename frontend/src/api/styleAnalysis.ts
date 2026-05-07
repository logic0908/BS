import axios from 'axios'

import type { StyleEvidenceCompareResponse } from '../types'

export async function compareStyleEvidence(params: {
  input_url?: string
  output_url?: string
  input_path?: string
  output_path?: string
  prompt_text: string
  model_preset_id?: string
}): Promise<StyleEvidenceCompareResponse> {
  const response = await axios.post<StyleEvidenceCompareResponse>('/api/v1/style-analysis/compare', params)
  return response.data
}
