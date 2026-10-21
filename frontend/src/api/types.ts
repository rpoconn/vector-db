import type { components } from './schema'

type Schemas = components['schemas']

export type ProductSummary = Schemas['ProductSummary']
export type ProductDetail = Schemas['ProductDetail']
export type ProductImage = Schemas['ProductImageOut']
export type ProductPage = Schemas['Page_ProductSummary_']
export type Category = Schemas['CategoryOut']
export type SearchHit = Schemas['SearchHit']
export type SearchResponse = Schemas['SearchResponse']
export type User = Schemas['UserRead']
export type OAuthProvider = Schemas['OAuthProviderOut']
export type OAuthEmailConfirmationSent = Schemas['OAuthEmailConfirmationSent']
export type ValidationError = Schemas['ValidationError']
