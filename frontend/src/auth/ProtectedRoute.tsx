/**
 * Protected Route Component.
 *
 * Wraps routes that require authentication.
 * Redirects to login if user is not authenticated.
 * Can optionally require specific roles.
 */
import React from 'react'
import { Box, CircularProgress, Typography, alpha } from '@mui/material'
import { useAuth } from './AuthProvider'

interface ProtectedRouteProps {
  /** Child components to render when authenticated */
  children: React.ReactNode
  /** Optional role required to access this route */
  requiredRole?: string
}

/**
 * Loading spinner displayed during authentication check.
 */
const LoadingSpinner: React.FC = () => (
  <Box
    display="flex"
    flexDirection="column"
    alignItems="center"
    justifyContent="center"
    minHeight="100vh"
    sx={{
      bgcolor: 'background.default',
    }}
  >
    <CircularProgress color="primary" size={48} thickness={4} />
    <Typography
      variant="body1"
      sx={{
        mt: 2,
        color: 'text.secondary',
      }}
    >
      Loading...
    </Typography>
  </Box>
)

/**
 * Unauthorized access message.
 */
const UnauthorizedMessage: React.FC<{ requiredRole?: string }> = ({ requiredRole }) => (
  <Box
    display="flex"
    flexDirection="column"
    alignItems="center"
    justifyContent="center"
    minHeight="100vh"
    sx={{
      bgcolor: 'background.default',
    }}
  >
    <Box
      sx={{
        p: 4,
        borderRadius: 2,
        bgcolor: (theme) => alpha(theme.palette.error.main, 0.1),
        border: 1,
        borderColor: 'error.main',
        textAlign: 'center',
      }}
    >
      <Typography variant="h5" color="error" gutterBottom>
        Access Denied
      </Typography>
      <Typography variant="body1" color="text.secondary">
        {requiredRole
          ? `You need the "${requiredRole}" role to access this page.`
          : 'You do not have permission to access this page.'}
      </Typography>
    </Box>
  </Box>
)

/**
 * Protected Route wrapper component.
 *
 * Usage:
 * ```tsx
 * <ProtectedRoute>
 *   <Dashboard />
 * </ProtectedRoute>
 *
 * <ProtectedRoute requiredRole="admin">
 *   <AdminPanel />
 * </ProtectedRoute>
 * ```
 */
export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, requiredRole }) => {
  const { isAuthenticated, isLoading, hasRole, login } = useAuth()

  // Show loading spinner while auth is initializing
  if (isLoading) {
    return <LoadingSpinner />
  }

  // If not authenticated, redirect to login
  if (!isAuthenticated) {
    // Trigger Keycloak login
    login()
    // Show loading while redirecting
    return <LoadingSpinner />
  }

  // If role is required but user doesn't have it, show unauthorized
  if (requiredRole && !hasRole(requiredRole)) {
    return <UnauthorizedMessage requiredRole={requiredRole} />
  }

  // User is authenticated and has required role (if any)
  return <>{children}</>
}

export default ProtectedRoute
