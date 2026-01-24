import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  Button,
  alpha,
  useTheme,
  Skeleton,
  Divider,
} from '@mui/material';
import {
  Save as SaveIcon,
  Settings as SettingsIcon,
  Memory as MemoryIcon,
} from '@mui/icons-material';
import { useModels, useUpdateModel } from '../hooks/useQueries';
import { Model } from '../types';

const Settings: React.FC = () => {
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.5);
  const theme = useTheme();

  // TanStack Query hooks for server state management
  const { data: models, isLoading } = useModels();
  const updateMutation = useUpdateModel();

  const handleSave = () => {
    if (selectedModel) {
      updateMutation.mutate({
        name: selectedModel,
        data: { confidence_threshold: confidenceThreshold },
      });
    }
  };

  if (isLoading) {
    return (
      <Box>
        <Skeleton variant="text" width={120} height={40} sx={{ mb: 3 }} />
        <Skeleton variant="rounded" height={300} />
      </Box>
    );
  }

  const modelList = models?.data || [];

  return (
    <Box className="fade-in">
      {/* Page Header */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 4,
          pb: 2,
          borderBottom: `1px solid ${alpha(theme.palette.divider, 0.5)}`,
        }}
      >
        <Box>
          <Typography
            variant="h4"
            sx={{
              fontWeight: 700,
              background: `linear-gradient(135deg, ${theme.palette.text.primary} 0%, ${theme.palette.secondary.main} 100%)`,
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            Settings
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Configure system and detection parameters
          </Typography>
        </Box>
      </Box>

      {/* Settings Cards */}
      <Box sx={{ display: 'grid', gap: 3 }}>
        {/* Object Detection Settings */}
        <Card>
          <CardContent sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
              <Box
                sx={{
                  width: 44,
                  height: 44,
                  borderRadius: 2,
                  background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.2)} 0%, ${alpha(theme.palette.primary.dark, 0.2)} 100%)`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <MemoryIcon sx={{ color: 'primary.main' }} />
              </Box>
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  Object Detection
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Configure AI model and detection sensitivity
                </Typography>
              </Box>
            </Box>

            <Divider sx={{ mb: 3 }} />

            <FormControl fullWidth sx={{ mb: 4 }}>
              <InputLabel>Detection Model</InputLabel>
              <Select
                value={selectedModel}
                label="Detection Model"
                onChange={(e) => setSelectedModel(e.target.value)}
              >
                {modelList.map((model: Model) => (
                  <MenuItem key={model.name} value={model.name}>
                    {model.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Box sx={{ mb: 4 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography sx={{ fontWeight: 500 }}>Confidence Threshold</Typography>
                <Typography
                  sx={{
                    fontWeight: 600,
                    color: 'primary.main',
                    backgroundColor: alpha(theme.palette.primary.main, 0.1),
                    px: 1.5,
                    py: 0.25,
                    borderRadius: 1,
                  }}
                >
                  {(confidenceThreshold * 100).toFixed(0)}%
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Minimum confidence level required for detections
              </Typography>
              <Slider
                value={confidenceThreshold}
                onChange={(_, value) => setConfidenceThreshold(value as number)}
                min={0}
                max={1}
                step={0.05}
                valueLabelDisplay="auto"
                valueLabelFormat={(value) => `${(value * 100).toFixed(0)}%`}
                sx={{
                  '& .MuiSlider-thumb': {
                    backgroundColor: theme.palette.primary.main,
                  },
                  '& .MuiSlider-track': {
                    background: `linear-gradient(90deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
                  },
                  '& .MuiSlider-rail': {
                    backgroundColor: alpha(theme.palette.primary.main, 0.2),
                  },
                }}
              />
            </Box>

            <Button
              variant="contained"
              onClick={handleSave}
              disabled={!selectedModel || updateMutation.isPending}
              startIcon={<SaveIcon />}
              sx={{ px: 4 }}
            >
              {updateMutation.isPending ? 'Saving...' : 'Save Settings'}
            </Button>
          </CardContent>
        </Card>

        {/* System Info Card */}
        <Card>
          <CardContent sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
              <Box
                sx={{
                  width: 44,
                  height: 44,
                  borderRadius: 2,
                  background: `linear-gradient(135deg, ${alpha(theme.palette.secondary.main, 0.2)} 0%, ${alpha(theme.palette.secondary.dark, 0.2)} 100%)`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <SettingsIcon sx={{ color: 'secondary.main' }} />
              </Box>
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  System Information
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  CARCARA-NVC application details
                </Typography>
              </Box>
            </Box>

            <Divider sx={{ mb: 3 }} />

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2" color="text.secondary">Product Name</Typography>
                <Typography variant="body2" sx={{ fontWeight: 600, color: 'primary.main' }}>CARCARA-NVC</Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2" color="text.secondary">Description</Typography>
                <Typography variant="body2" sx={{ fontWeight: 500 }}>Network Video Controller</Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="body2" color="text.secondary">Version</Typography>
                <Typography variant="body2" sx={{ fontWeight: 500 }}>1.0.0</Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
};

export default Settings;