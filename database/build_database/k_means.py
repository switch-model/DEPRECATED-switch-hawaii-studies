"""
Code for clustering sites into natural groups.
Based on https://datasciencelab.wordpress.com/2014/01/15/improved-seeding-for-clustering-with-k-means/
but with weighting (we act as if there are many points at the large wind/solar sites).
"""

import numpy as np
from collections import defaultdict

class KMeans():
    def __init__(self, K, X, size=None):
    	if size is None:
            size = np.ones(len(X), dtype=float)
        self.X = np.array(X, dtype=float)
        # choose up to K clusters, but not more than the number of unique elements in X
        self.K = min(K, len(set(tuple(x) for x in self.X)))
        self.size = np.array(size, dtype=float)
        self.N = len(X)
        self.mu = np.array([])
        self.clusters = None
        self.method = None
            
            
    def _squared_distances(self):
        """ 
        return a matrix with one row for each entry in self.X and one column for each entry in self.mu,
        showing the squared distance between the corresponding entries in X and mu
        """ 
        # below is equivalent to
        # D2 = np.array([
        #     np.sum((x - self.mu)**2, axis=1) for x in X
        # ])
        return ((self.X[:,np.newaxis,:] - self.mu[np.newaxis,:,:])**2).sum(axis=2)
        
    def _choose_next_center(self):
        # act as if there are a number of points at each location, 
        # proportional to the specified sizes
        weights = np.copy(self.size)
        if len(self.mu) > 0:
            # one or more centers have already been selected
            # give extra weight to the points far from the existing centers
            # (why not just choose the furthest-away point?)
            weights *= self._squared_distances().min(axis=1)

        # choose a random point to add
        i = np.random.choice(self.X.shape[0], p=weights/np.sum(weights))
        x = self.X[i]

        if len(self.mu) > 0:
            # note: it's messy to keep re-creating mu as a numpy array,
            # but even if we used a list instead, that would get converted implicitly
            # to an array in the _squared_distances() calculation
            self.mu = np.append(self.mu, [x], axis=0)
        else:
            # no easy way to append a row array to an empty numpy array...
            self.mu = np.array([x])

    def init_centers(self, method='++'):
        self.method = method
        if method == 'random':
            # Initialize to K random centers (weighted by the project size at each location)
            self.mu = np.random.choice(self.X, size=self.K, p=self.size)
        else:   # method == '++'
            # initialize the centers using the k-means++ technique from 
            # Arthur and Vassilvitskii (2007)
            # http://theory.stanford.edu/~sergei/papers/kMeansPP-soda.pdf
            while len(self.mu) < self.K:
                self._choose_next_center()

    def _cluster_points(self):
        self.clusters = defaultdict(list)
        best_mu_idx = self._squared_distances().argmin(axis=1)
        for i, x in enumerate(self.X):
            self.clusters[best_mu_idx[i]].append(x)
        self.cluster_id = best_mu_idx   # save cluster identifiers for plotting
 
    def _reevaluate_centers(self):
        for i in range(len(self.mu)):
            self.mu[i] = np.mean(self.clusters[i], axis=0)
 
    def _group_mean(a, groups, n_groups, weights):
        return (
            np.bincount(groups, weights=a*weights, minlength=n_groups) 
            / np.bincount(groups, weights=weights, minlength=n_groups)
        )
    
    def calculate_clusters(self):
        # find the id of the nearest cluster (0 to K-1) for each entry in X
        self.cluster_id = self._squared_distances().argmin(axis=1)
        # get weighted mean values of the X's that correspond to each cluster id 
        self.mu[i] = np.apply_along_axis(
            self._group_mean, axis=1, arr=self.X, 
            groups=self.cluster_id, n_groups=self.K, weights=self.size
        )

    def find_centers(self):
        while True:
            oldmu = np.copy(self.mu)
            # Assign all points in X to clusters
            self._cluster_points()
            # Reevaluate centers
            self._reevaluate_centers()
            # check for convergence
            if np.array_equal(oldmu, self.mu):
                break
        return self.mu

    def plot(self):
        import matplotlib.pyplot as plt
        from scipy.spatial import Voronoi, voronoi_plot_2d
        # print "self.X:"
        # print self.X
        # print "self.size:"
        # print self.size
        fig = plt.figure(figsize=(10,8), dpi=96)
        ax = fig.add_subplot(111)
        # self.fig, self.ax = plt.subplots(1, 1)
        # self.fig.set_size_inches(10, 8)
        vor = Voronoi(self.mu)
        vor_plot = voronoi_plot_2d(vor, ax=ax)
        # remove the markers for each cluster and for the vertices
        ax.get_lines()[1].remove()
        #ax.get_lines()[0].remove()
        ax.scatter(x=self.X[:,0], y=self.X[:,1], c=self.cluster_id, s=self.size, alpha=0.75)
        ax.set_xlim(min(self.X[:,0]), max(self.X[:,0]))
        ax.set_ylim(min(self.X[:,1]), max(self.X[:,1]))
        # canvas.draw()   # may not be needed? see http://stackoverflow.com/questions/26783843/redrawing-a-plot-in-ipython-matplotlib
        