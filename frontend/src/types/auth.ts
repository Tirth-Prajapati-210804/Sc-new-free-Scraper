export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

