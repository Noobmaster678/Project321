import { expect, test } from '@playwright/test';
import os from 'node:os';
import path from 'node:path';
import { mkdtemp, writeFile } from 'node:fs/promises';
import { installMockApi, withAuthToken } from './mockApi';

test('dashboard renders key stats', async ({ page }) => {
  await installMockApi(page);
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  await expect(page.getByText('Total Images')).toBeVisible();
  await expect(page.getByText('Quoll Detections')).toBeVisible();
});

test('image browser supports quoll-only filter', async ({ page }) => {
  await installMockApi(page);
  await page.goto('/images');

  await expect(page.getByRole('heading', { name: 'Image Browser' })).toBeVisible();
  await page.getByRole('combobox').nth(2).selectOption('quoll');
  await expect(page.getByText('1 images')).toBeVisible();
});

test('reference comparison ignores a stale gallery response', async ({ page }) => {
  await page.route('**/api/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    const respond = (payload: unknown) => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(payload),
    });

    if (pathname.endsWith('/api/images/by-species/quoll')) {
      return respond({
        items: [{
          id: 1,
          filename: 'quoll.jpg',
          file_path: 'uploads/quoll.jpg',
          camera_id: 1,
          collection_id: 1,
          captured_at: null,
          width: 1920,
          height: 1080,
          processed: true,
          has_animal: true,
          thumbnail_path: null,
        }],
        total: 1,
        page: 1,
        per_page: 30,
        pages: 1,
      });
    }
    if (pathname.endsWith('/api/images/1')) {
      return respond({
        id: 1,
        filename: 'quoll.jpg',
        file_path: 'uploads/quoll.jpg',
        processed: true,
        has_animal: true,
        detections: [{
          id: 10,
          image_id: 1,
          bbox_x: 0.1,
          bbox_y: 0.1,
          bbox_w: 0.5,
          bbox_h: 0.5,
          detection_confidence: 0.95,
          category: 'animal',
          species: 'quoll',
          classification_confidence: 0.9,
          model_version: 'test',
          crop_path: 'crops/quoll.jpg',
          review_status: 'verified',
          created_at: null,
          annotations: [],
        }],
      });
    }
    if (pathname.endsWith('/api/stats/individuals')) {
      return respond([
        { individual_id: 'A', species: 'quoll', first_seen: null, last_seen: null, total_sightings: 1 },
        { individual_id: 'B', species: 'quoll', first_seen: null, last_seen: null, total_sightings: 1 },
      ]);
    }
    if (pathname.endsWith('/api/stats/individuals/A/gallery')) {
      await new Promise((resolve) => setTimeout(resolve, 300));
      return respond({
        individual_id: 'A',
        source: 'annotations',
        items: [{ image_id: 101, detection_id: 101, captured_at: null, thumb_url: null, crop_url: null, display_url: '/storage/reference-a.jpg' }],
      });
    }
    if (pathname.endsWith('/api/stats/individuals/B/gallery')) {
      await new Promise((resolve) => setTimeout(resolve, 20));
      return respond({
        individual_id: 'B',
        source: 'annotations',
        items: [{ image_id: 202, detection_id: 202, captured_at: null, thumb_url: null, crop_url: null, display_url: '/storage/reference-b.jpg' }],
      });
    }
    if (pathname.includes('/api/reid/detections/10/suggestions')) {
      return respond({
        detection_id: 10,
        suggestions: [],
        gate_accepts_top1: false,
        sim_threshold: 0.8,
        gap_threshold: 0.1,
        gap: 0,
      });
    }
    return respond({});
  });

  await page.goto('/individuals/species/quoll/images');
  await page.getByText('quoll.jpg').click();
  const comparison = page.getByText('Reference comparison').locator('..');
  const picker = comparison.getByRole('combobox');
  await picker.selectOption('A');
  await picker.selectOption('B');

  await expect(comparison.locator('img[src="/storage/reference-b.jpg"]')).toBeVisible();
  await page.waitForTimeout(350);
  await expect(comparison.locator('img[src="/storage/reference-b.jpg"]')).toBeVisible();
  await expect(comparison.locator('img[src="/storage/reference-a.jpg"]')).toHaveCount(0);
});

test('detections page shows species distribution', async ({ page }) => {
  await installMockApi(page);
  await page.goto('/detections');

  await expect(page.getByRole('heading', { name: 'Detections' })).toBeVisible();
  await expect(page.getByText('Species Distribution')).toBeVisible();
  await expect(page.getByText('Spotted-tailed Quoll')).toBeVisible();
});

test('reports page renders export actions', async ({ page }) => {
  await installMockApi(page);
  await page.goto('/reports');

  await expect(page.getByRole('heading', { name: 'Reports' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Report CSV' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Quoll Detections CSV' })).toBeVisible();
});

test('batch upload works from folder input', async ({ page }) => {
  await withAuthToken(page);
  await installMockApi(page);
  await page.goto('/upload');

  const tempDir = await mkdtemp(path.join(os.tmpdir(), 'wildlife-upload-'));
  await writeFile(path.join(tempDir, 'cam1_001.jpg'), 'a');
  await writeFile(path.join(tempDir, 'cam1_002.jpg'), 'b');

  const folderInput = page.locator('input[webkitdirectory]').first();
  await folderInput.setInputFiles(tempDir);

  await page.getByRole('button', { name: 'Upload & Process' }).click();
  await expect(page.getByText(/Job #55/)).toBeVisible();
  await expect(page.getByText('2 / 2 processed')).toBeVisible();
});

test('admin panel is accessible for admin role', async ({ page }) => {
  await withAuthToken(page);
  await installMockApi(page, 'admin');
  await page.goto('/admin');

  await expect(page.getByRole('heading', { name: 'Admin Panel' })).toBeVisible();
  await expect(page.getByText('System management and user administration')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Users' })).toBeVisible();
});
