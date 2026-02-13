/**
 * Login Page Component.
 *
 * Displays a login button that redirects to Keycloak.
 * Redirects authenticated users to the home page.
 */
import React from 'react'
import { Navigate } from 'react-router-dom'
import { Box, Button, Card, CardContent, Typography, CircularProgress, alpha } from '@mui/material'
import LockOutlinedIcon from '@mui/icons-material/LockOutlined'
import { useAuth } from '../auth'

const Login: React.FC = () => {
  const { isAuthenticated, isLoading, login } = useAuth()

  // Show loading while auth is initializing
  if (isLoading) {
    return (
      <Box
        display="flex"
        alignItems="center"
        justifyContent="center"
        minHeight="100vh"
        sx={{ bgcolor: 'background.default' }}
      >
        <CircularProgress color="primary" />
      </Box>
    )
  }

  // Redirect to home if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  return (
    <Box
      display="flex"
      alignItems="center"
      justifyContent="center"
      minHeight="100vh"
      sx={{
        bgcolor: 'background.default',
        background: (theme) => `
          radial-gradient(
            circle at 50% 50%,
            ${alpha(theme.palette.primary.main, 0.1)} 0%,
            transparent 50%
          ),
          ${theme.palette.background.default}
        `,
      }}
    >
      <Card
        sx={{
          maxWidth: 400,
          width: '100%',
          mx: 2,
          bgcolor: 'background.paper',
          boxShadow: (theme) => `0 8px 32px ${alpha(theme.palette.common.black, 0.3)}`,
        }}
      >
        <CardContent sx={{ textAlign: 'center', py: 5, px: 4 }}>
          {/* Logo/Icon */}
          <Box
            sx={{
              width: 80,
              height: 80,
              borderRadius: '50%',
              bgcolor: (theme) => alpha(theme.palette.primary.main, 0.1),
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              mx: 'auto',
              mb: 3,
            }}
          >
            <LockOutlinedIcon
              sx={{
                fontSize: 40,
                color: 'primary.main',
              }}
            />
          </Box>

          {/* Title */}
          <Typography
            variant="h4"
            gutterBottom
            sx={{
              fontWeight: 700,
              color: 'text.primary',
            }}
          >
            Carcara NVC
          </Typography>

          {/* Subtitle */}
          <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
            Network Video Controller
          </Typography>

          {/* Login Button */}
          <Button
            variant="contained"
            color="primary"
            size="large"
            onClick={login}
            fullWidth
            sx={{
              py: 1.5,
              fontSize: '1rem',
              fontWeight: 600,
              textTransform: 'none',
            }}
          >
            Sign In
          </Button>

          {/* Footer text */}
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{
              display: 'block',
              mt: 3,
            }}
          >
            Secure authentication powered by Keycloak
          </Typography>
        </CardContent>
      </Card>
    </Box>
  )
}

export default Login
