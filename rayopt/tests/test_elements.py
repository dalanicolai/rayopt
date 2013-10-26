# -*- coding: utf8 -*-
#
#   pyrayopt - raytracing for optical imaging systems
#   Copyright (C) 2013 Robert Jordens <jordens@phys.ethz.ch>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import (absolute_import, print_function,
        unicode_literals, division)

import os
import unittest

from scipy import constants as ct
import numpy as np
from numpy import testing as nptest


from rayopt import Spheroid, Aperture, ModelMaterial, mirror
from rayopt.utils import sinarctan, tanarcsin


class TransformCase(unittest.TestCase):
    def setUp(self):
        self.s = Spheroid(distance=2., direction=(1, 3, 4.),
                angles=(.3, .2, .1))

    def test_offset(self):
        nptest.assert_allclose(self.s.offset,
                self.s.distance*self.s.direction)
    
    def test_from_to_axis(self, n=10):
        x = np.random.randn(n, 3)
        x1 = self.s.to_axis(x)
        x2 = self.s.from_axis(x1)
        nptest.assert_allclose(x, x2)

    def test_from_to_normal(self, n=10):
        x = np.random.randn(n, 3)
        x1 = self.s.to_normal(x)
        x2 = self.s.from_normal(x1)
        nptest.assert_allclose(x, x2)

    def test_rot(self):
        self.s.angles = None
        x = np.array([0., 0, 3])
        x1 = self.s.from_normal(x)
        nptest.assert_allclose(x1, self.s.direction*3)
        self.s.direction = 0, 0, 1.
        self.s.angles = .1, 0, 0
        x1 = self.s.from_normal(x)
        nptest.assert_allclose(x1, (0, 3*np.sin(.1), 3*np.cos(.1)))


class ParaxialCase(unittest.TestCase):
    def setUp(self):
        self.mat = mat = ModelMaterial(nd=1.5, vd=np.inf)
        self.s0 = Spheroid(curvature=0., distance=0., material=mat)
        self.s = Spheroid(curvature=.1, distance=0, material=mat)
        self.sm0 = Spheroid(curvature=0, distance=0, material=mirror)
        self.sm = Spheroid(curvature=.1, distance=0, material=mirror)

    def test_offset(self):
        nptest.assert_allclose(self.s.direction, (0, 0, 1))
        nptest.assert_allclose(self.s.distance, 0)
        nptest.assert_allclose(self.s.offset, 0)
    
    def test_rotation(self):
        self.assertEqual(self.s.angles, None)
        nptest.assert_allclose(self.s.from_axis([0, 0, 1]), (0, 0, 1))
        nptest.assert_allclose(self.s.from_normal([0, 0, 1]), (0, 0, 1))

    def test_snell_paraxial(self):
        y0, u0 = (1, 2), (.2, .1)
        yu, n = self.s0.propagate_paraxial(np.hstack((y0, u0)), 1., 1.)
        y, u = np.hsplit(yu, 2)
        mu = 1/self.s0.material.nd
        nptest.assert_allclose(y, y0)
        nptest.assert_allclose(u/mu, u0)

    def test_snell_paraxial_mirror(self):
        y0, u0 = (1, 2), (.2, .1)
        yu, n = self.sm0.propagate_paraxial(np.hstack((y0, u0)), 1., 1.)
        y, u = np.hsplit(yu, 2)
        nptest.assert_allclose(-y, y0)
        nptest.assert_allclose(-u, u0)

    def test_align(self):
        d = 0, -.1, 1
        d /= np.linalg.norm(d)
        mu = 1/self.s0.material.nd
        self.s0.align(d, mu)
        e = self.s0.from_normal(self.s0.excidence(mu))
        nptest.assert_allclose(e, d)
        y0, u0 = (1, 2), (.2, .0)
        yu, n = self.s0.propagate_paraxial(np.hstack((y0, u0)), 1., 1.)
        y, u = np.hsplit(yu, 2)
        nptest.assert_allclose(y[0], y0[0])
        nptest.assert_allclose(u[0]/mu, u0[0])
        nptest.assert_allclose(u[1]/mu, d[0])


class ParaxToRealCase(unittest.TestCase):
    def setUp(self):
        self.mat = mat = ModelMaterial(nd=1.5, vd=np.inf)
        d = np.random.randn(3)*1e-1 + (0, 0, 1.)
        a = np.random.randn(3)*1e-8
        a[1:] = 0
        self.s = Spheroid(curvature=.1, distance=.2, material=mat,
                direction=d, angles=a)
        de = self.s.excidence(1/self.s.material.nd)
        self.sa = Spheroid(direction=de)

    def test_real_similar_to_parax(self, n=10, e=1e-8):
        y0p = np.random.randn(n, 2.)*e
        u0p = np.random.randn(n, 2.)*e
        y0r = np.hstack((y0p, np.ones((n, 1))*-self.s.distance))
        u0r = np.hstack((sinarctan(u0p), np.zeros((n, 1))))
        u0r[:, 2] = np.sqrt(1 - np.square(u0p).sum(1))
        yup, np_ = self.s.propagate_paraxial(np.hstack((y0p, u0p)), 1., 1.)
        yp, up = np.hsplit(yup, 2)
        #y0r, u0r = self.s.to_normal(y0r, u0r)
        yr, ur, nr, tr  = self.s.propagate(y0r, u0r, 1., 1.)
        #yr, ur = self.s.from_normal(yr, ur)
        yr, ur = self.sa.to_axis(yr, ur)
        nptest.assert_allclose(nr, np_)
        nptest.assert_allclose(yr[:, :2], yp)
        nptest.assert_allclose(tanarcsin(ur), up)


class PupilCase(unittest.TestCase):
    def setUp(self):
        self.sf = Spheroid(radius=3.)
        self.si = Spheroid(angular_radius=np.deg2rad(60))
        self.sl = Spheroid(angular_radius=np.deg2rad(105))
        self.sn = Spheroid(distance=2., radius=1.5)

    def aim_prop(self, s, yo, yp):
        z = self.sn.distance
        h = self.sn.radius
        a = np.arctan2(h, z)
        y, u = s.aim(yo, yp, z, a)
        nptest.assert_allclose(np.square(u).sum(1), 1)
        y1 = y - (0, 0, z)
        y1, u1, n1, t1 = self.sn.propagate(y1, u, 1., 1.)
        nptest.assert_allclose(np.square(u1).sum(1), 1)
        if s.finite:
            y[:, :2] /= s.radius
            nptest.assert_allclose(np.sign(y[:, 2]),
                    np.sign(s.curvature))
        if self.sn.finite:
            y1[:, :2] /= self.sn.radius
            nptest.assert_allclose(np.sign(y1[:, 2]),
                    np.sign(self.sn.curvature))
        return y[0], u[0], y1[0], u1[0]

    def test_pupil(self):
        yo, yp = (0, .8), (0, 0)
        y, u, y1, u1 = self.aim_prop(self.sf, yo, yp)
        nptest.assert_allclose(-y[:2], yo)
        nptest.assert_allclose(y1[:2], yp)

        yo, yp = (0, .0), (0, 1.)
        y, u, y1, u1 = self.aim_prop(self.sf, yo, yp)
        nptest.assert_allclose(-y[:2], yo)
        nptest.assert_allclose(y1[:2], yp)

