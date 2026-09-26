import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { authApi } from '../api/auth';
import { queryKeys } from '../api/queryKeys';
import type { UserCreate, UserUpdate } from '../types';

export const useAuthUsers = () => {
  return useQuery({
    queryKey: queryKeys.authUsers(),
    queryFn: authApi.listUsers,
  });
};

export const useCreateAuthUser = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: UserCreate) => authApi.createUser(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.authUsers() });
    },
  });
};

export const useUpdateAuthUser = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ userId, patch }: { userId: number; patch: UserUpdate }) => authApi.updateUser(userId, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.authUsers() });
    },
  });
};
