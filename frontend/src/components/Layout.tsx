import React from 'react';
import {
  AppBar,
  Box,
  CssBaseline,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  alpha,
  useTheme,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Videocam as CameraIcon,
  PlayCircle as StreamIcon,
  Notifications as AlarmIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';

const drawerWidth = 260;

interface LayoutProps {
  children: React.ReactNode;
}

// CARCARA Logo Component
const CarcaraLogo: React.FC<{ size?: 'small' | 'large' }> = ({ size = 'large' }) => {
  const theme = useTheme();
  const isSmall = size === 'small';

  return (
    <Box sx={{
      display: 'flex',
      alignItems: 'center',
      gap: isSmall ? 1 : 1.5,
      py: isSmall ? 0 : 1,
    }}>
      {/* Logo Icon - Bird/Hawk silhouette representing Carcara */}
      <Box
        sx={{
          width: isSmall ? 32 : 44,
          height: isSmall ? 32 : 44,
          borderRadius: '10px',
          background: `linear-gradient(135deg, #F5A45A 0%, #D26A27 100%)`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: `0 4px 12px ${alpha('#D26A27', 0.4)}`,
          position: 'relative',
          overflow: 'hidden',
          '&::before': {
            content: '""',
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'linear-gradient(180deg, rgba(255,255,255,0.2) 0%, transparent 50%)',
          },
        }}
      >
        {/* Stylized "C" for Carcara */}
        <Typography
          sx={{
            fontSize: isSmall ? '1.2rem' : '1.6rem',
            fontWeight: 800,
            color: '#181A1F',
            fontFamily: '"Inter", sans-serif',
            letterSpacing: '-0.05em',
            position: 'relative',
            zIndex: 1,
          }}
        >
          C
        </Typography>
      </Box>

      {/* Brand Text */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        <Typography
          variant={isSmall ? 'subtitle1' : 'h6'}
          sx={{
            fontWeight: 700,
            letterSpacing: '0.08em',
            color: theme.palette.text.primary,
            lineHeight: 1.1,
            fontSize: isSmall ? '0.95rem' : '1.15rem',
          }}
        >
          CARCARA
        </Typography>
        <Typography
          sx={{
            fontSize: isSmall ? '0.6rem' : '0.7rem',
            fontWeight: 600,
            letterSpacing: '0.15em',
            color: '#F5A45A',
            lineHeight: 1,
          }}
        >
          NVC
        </Typography>
      </Box>
    </Box>
  );
};

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const menuItems = [
    { text: 'Cameras', icon: <CameraIcon />, path: '/cameras' },
    { text: 'Streams', icon: <StreamIcon />, path: '/streams' },
    { text: 'Alarms', icon: <AlarmIcon />, path: '/alarms' },
    { text: 'Settings', icon: <SettingsIcon />, path: '/settings' },
  ];

  const isActive = (path: string) => location.pathname === path || (path === '/cameras' && location.pathname === '/');

  const drawer = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Logo Section */}
      <Box
        sx={{
          p: 2.5,
          display: 'flex',
          alignItems: 'center',
          borderBottom: `1px solid ${alpha(theme.palette.divider, 0.5)}`,
        }}
      >
        <CarcaraLogo />
      </Box>

      {/* Navigation */}
      <Box sx={{ flex: 1, py: 2 }}>
        <Typography
          variant="overline"
          sx={{
            px: 3,
            py: 1,
            display: 'block',
            color: theme.palette.text.secondary,
            fontSize: '0.65rem',
            letterSpacing: '0.1em',
          }}
        >
          Main Menu
        </Typography>
        <List sx={{ px: 1 }}>
          {menuItems.map((item) => (
            <ListItem key={item.text} disablePadding sx={{ mb: 0.5 }}>
              <ListItemButton
                onClick={() => navigate(item.path)}
                selected={isActive(item.path)}
                sx={{
                  borderRadius: 2,
                  py: 1.25,
                  '&.Mui-selected': {
                    backgroundColor: alpha(theme.palette.primary.main, 0.12),
                    '&::before': {
                      content: '""',
                      position: 'absolute',
                      left: 0,
                      top: '50%',
                      transform: 'translateY(-50%)',
                      width: 3,
                      height: '60%',
                      borderRadius: '0 4px 4px 0',
                      backgroundColor: theme.palette.primary.main,
                    },
                  },
                }}
              >
                <ListItemIcon
                  sx={{
                    color: isActive(item.path) ? theme.palette.primary.main : theme.palette.text.secondary,
                    minWidth: 40,
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.text}
                  primaryTypographyProps={{
                    fontWeight: isActive(item.path) ? 600 : 500,
                    fontSize: '0.9rem',
                    color: isActive(item.path) ? theme.palette.text.primary : theme.palette.text.secondary,
                  }}
                />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Box>

      {/* Footer */}
      <Box
        sx={{
          p: 2,
          borderTop: `1px solid ${alpha(theme.palette.divider, 0.5)}`,
          textAlign: 'center',
        }}
      >
        <Typography
          variant="caption"
          sx={{ color: theme.palette.text.secondary, fontSize: '0.7rem' }}
        >
          Network Video Controller
        </Typography>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      <CssBaseline />
      <AppBar
        position="fixed"
        sx={{
          width: { sm: `calc(100% - ${drawerWidth}px)` },
          ml: { sm: `${drawerWidth}px` },
          backdropFilter: 'blur(8px)',
          backgroundColor: alpha(theme.palette.background.paper, 0.9),
        }}
      >
        <Toolbar sx={{ justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <IconButton
              color="inherit"
              aria-label="open drawer"
              edge="start"
              onClick={handleDrawerToggle}
              sx={{ mr: 2, display: { sm: 'none' } }}
            >
              <MenuIcon />
            </IconButton>
            <Box sx={{ display: { xs: 'block', sm: 'none' } }}>
              <CarcaraLogo size="small" />
            </Box>
          </Box>

          {/* Page Title - Shows current page */}
          <Typography
            variant="h6"
            sx={{
              display: { xs: 'none', sm: 'block' },
              fontWeight: 600,
              color: theme.palette.text.primary,
            }}
          >
            {menuItems.find(item => isActive(item.path))?.text || 'Dashboard'}
          </Typography>

          {/* Placeholder for future actions */}
          <Box sx={{ width: 48 }} />
        </Toolbar>
      </AppBar>
      <Box
        component="nav"
        sx={{ width: { sm: drawerWidth }, flexShrink: { sm: 0 } }}
      >
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{
            keepMounted: true,
          }}
          sx={{
            display: { xs: 'block', sm: 'none' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: drawerWidth,
            },
          }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', sm: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: drawerWidth,
            },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { sm: `calc(100% - ${drawerWidth}px)` },
          minHeight: '100vh',
        }}
      >
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
};

export default Layout;