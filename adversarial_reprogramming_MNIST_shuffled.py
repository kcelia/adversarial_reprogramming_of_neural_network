import random
import numpy as np

import torch 
import torch as T
import torch.nn as nn

import torchvision
from torchvision import datasets, transforms
from torch.utils.data import Dataset

from tqdm import tqdm
from random import shuffle

import matplotlib.pyplot as plt

import scipy
import scipy.misc as misc

from scipy.ndimage import gaussian_filter

from utils import get_program, get_mask, x_to_X, train, reg_l1, reg_l2


def shuffle_mnist(p, seed=23):
    """
    This function shuffle an image data

    :param p: the image that will be shuffled
    :param seed: we use a random seed to have the same shuffling at each call of the function

    :type p: torch.tensor
    :type seed: int

    :return: a shuffled image
    :rtype: torch.tensor
    """
    lst = [(i,j) for i in  range(p.shape[1]) for j in range(p.shape[2])]
    random.Random(seed).shuffle(lst)

    plan = {
        (i, j): lst[i * p.shape[1] + j] 
        for i in  range(p.shape[1]) for j in range(p.shape[2])
    }

    out = T.zeros(p.shape)
    for ((i, j), (ii, jj)) in plan.items():
        out[:, i, j] = p[:, ii, jj]

    return out

def get_mnist(batch_size):
    """
    This function retruns the train and test loader of mnist 
    dataset for a given batch_size

    :param batch_size: size of the batch for data loader
    
    :type batch_size: int

    :return: train and test loader
    :rtype: tuple[torch.utils.data.DataLoader]
    """
    train_loader = T.utils.data.DataLoader(datasets.MNIST(
        './data', train=True, download=True,
        transform=transforms.Compose([
            transforms.ToTensor(), 
            transforms.Normalize((0.1307,), (0.3081,))
        ])),
        batch_size=batch_size, shuffle=True
    ) 
    test_loader = T.utils.data.DataLoader(datasets.MNIST(
        './data', train=False, download=True,
        transform=transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.1307,), (0.3081,))
        ])),
        batch_size=batch_size, shuffle=True
    ) 
    return train_loader, test_loader

class ProgrammingShuffledNetwork(nn.Module):
    """
    This class is the module that contains the network
    that will be uilized and the associated programm 
    that will be learned to hijak the first one
    with a shuffled input
    """

    def __init__(self, pretained_model, input_size, patch_size, channel_out=3, blur_sigma=0.,device='cpu'):
        """
        Constructor

        :param pretrained_model: the model to hitjak
        :param input_size: the img's size excepected by pretrained_model
        :param patch_size: the size of the small target domain img
        :param channel_out: nb channel
        :param blur_sigma: 0 if no bluring else the sigma used to blur the program before training
        :param device: device used for training
        
        :type pretrained_model: modul
        :type input_size: int
        :type patch_size: int
        :type channel_out: int
        :type blur_sigma: float
        :type device: str
        """
        super().__init__()
        self.device = device
        self.blur_sigma = blur_sigma
        self.model = pretained_model.to(self.device)
        self.p = T.autograd.Variable(T.randn((channel_out, input_size, input_size)).to(self.device), requires_grad=True)
        if blur_sigma:
            program = self.p.to("cpu").detach().permute(1, 2, 0).numpy()
            program = gaussian_filter(program, self.blur_sigma)
            program = T.tensor(program).float().permute(2, 0, 1)
            self.p = program
            
        self.mask = shuffle_mnist(get_mask(patch_size, input_size, channel_out, batch_size=1)[0])
        self.input_size = input_size
        self.mask.requires_grad = False

    def forward(self, x):
        x = T.tensor([shuffle_mnist(xx).numpy() for xx in x])
        #P = tanh (W + M)
        P = nn.Tanh()((1 - self.mask) * self.p) 
        #Xadv = hf (˜x; W) = X˜ + P
        x_adv = x_to_X(x, self.input_size, self.p.shape[0]).to(self.device) + P
        return self.model(x_adv)

DEVICE = 'cpu'
PATH = "./models/squeezenet1_0_MNIST_shuffled"

batch_size = 16
train_loader, test_loader = get_mnist(batch_size)

pretrained_model = torchvision.models.squeezenet1_0(pretrained=True).eval()

input_size = 224
patch_size = 36

model = ProgrammingShuffledNetwork(pretrained_model, input_size, patch_size, blur_sigma=.5)
optimizer = T.optim.Adam([model.p])

nb_epochs = 20
nb_freq = 10
model, loss_history = train(
    model, train_loader, nb_epochs, optimizer,
    C=.05, reg_fun=reg_l2,
    save_freq=nb_freq, 
    save_path=PATH, test_loader=test_loader, device=DEVICE
)

program = get_program(model, PATH, imshow=True)

