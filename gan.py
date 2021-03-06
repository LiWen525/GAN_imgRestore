#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import argparse
from random import sample
import os,random
import numpy as np
import theano as th
import theano.tensor as T
from keras.utils import np_utils
import keras.models as models
from keras.layers import Input,merge
from keras.layers.core import Reshape,Dense,Dropout,Activation,Flatten,Dense
from keras.layers.advanced_activations import LeakyReLU
from keras.activations import *
from keras.layers.wrappers import TimeDistributed
from keras.layers.noise import GaussianNoise
from keras.layers.convolutional import Convolution2D, MaxPooling2D, ZeroPadding2D, UpSampling2D
from keras.layers.recurrent import LSTM
from keras.regularizers import *
from keras.layers.normalization import *
from keras.optimizers import *
import matplotlib.pyplot as plt
import seaborn as sns
import random, sys, keras
from keras.models import Model,model_from_json
from keras.utils import np_utils
from tqdm import tqdm

from utils import *
from math import *
import cv2

WINDOW_WIDTH=int(32)
WINDOW_HEIGHT=int(32)

def build_generative_model():
    # Build Generative model ...
    nch = 3
    g_input = Input(shape=[WINDOW_HEIGHT,WINDOW_WIDTH,nch])

    H = Convolution2D(64, (3, 3), subsample=(1, 1), border_mode = 'same', activation='relu')(g_input)
    H = LeakyReLU(0.2)(H)

    H = Dropout(dropout_rate)(H)
    H = Convolution2D(64, (3, 3), subsample=(1, 1), border_mode = 'same', activation='relu')(H)
    H = LeakyReLU(0.2)(H)

    H = Dropout(dropout_rate)(H)
    H = Convolution2D(48, (3, 3), subsample=(1, 1), border_mode = 'same', activation='relu')(H)
    H = LeakyReLU(0.2)(H)

    H = Dropout(dropout_rate)(H)
    H = Convolution2D(32, (5, 5), subsample=(1, 1), border_mode = 'same', activation='relu')(H)
    H = LeakyReLU(0.2)(H)

    H = Dropout(dropout_rate)(H)
    H = Convolution2D(3, (5, 5), subsample=(1, 1), border_mode = 'same', activation='relu')(H)
    g_V = LeakyReLU(0.2)(H)

    # g_V = Reshape( (WINDOW_HEIGHT,WINDOW_WIDTH,nch) )(H)
    generator = Model(g_input,g_V)
    # generator.compile(loss='mean_squared_error', optimizer=opt)
    generator.compile(loss='binary_crossentropy', optimizer=opt)
    generator.summary()

    return generator

def build_discriminative_model():
    # Build Discriminative model ...
    d_input = Input(shape=[WINDOW_HEIGHT,WINDOW_WIDTH,3])
    H = Convolution2D(256, 5, 5, subsample=(2, 2), border_mode = 'same', activation='relu')(d_input)
    H = LeakyReLU(0.2)(H)
    H = Dropout(dropout_rate)(H)
    H = Convolution2D(512, 5, 5, subsample=(2, 2), border_mode = 'same', activation='relu')(H)
    H = LeakyReLU(0.2)(H)
    H = Dropout(dropout_rate)(H)
    H = Flatten()(H)
    H = Dense(256)(H)
    H = LeakyReLU(0.2)(H)
    H = Dropout(dropout_rate)(H)
    d_V = Dense(2,activation='softmax')(H)
    discriminator = Model(d_input,d_V)
    discriminator.compile(loss='categorical_crossentropy', optimizer=dopt)
    discriminator.summary()
    return discriminator


def make_trainable(net, val):
    net.trainable = val
    for l in net.layers:
        l.trainable = val



def train_for_n(generator,discriminator,GAN,nb_epoch=5000, plt_frq=25,BATCH_SIZE=32):
    pre_data=produce_data_bacth(20000)
    X_train=pre_data[0]

    ntrain = 1000
    trainidx = random.sample(range(0,X_train.shape[0]), ntrain)
    XT = X_train[trainidx,:,:,:]

    print("pre train the discriminator network")
    # Pre-train the discriminator network ...
    noise_gen = pre_data[1][:ntrain]
    generated_images = generator.predict(noise_gen)
    X = np.concatenate((XT, generated_images))
    n = XT.shape[0]
    y = np.zeros([2*n,2])
    y[:n,1] = 1
    y[n:,0] = 1

    generator.fit(noise_gen,pre_data[0][:ntrain], epochs=15, batch_size=128)

    make_trainable(discriminator,True)
    for _ in range(0):
        discriminator.fit(X,y, nb_epoch=1, batch_size=128)

    y_hat = discriminator.predict(X)

    # Measure accuracy of pre-trained discriminator network
    y_hat_idx = np.argmax(y_hat,axis=1)
    y_idx = np.argmax(y,axis=1)
    diff = y_idx-y_hat_idx
    n_tot = y.shape[0]
    n_rig = (diff==0).sum()
    acc = n_rig*100.0/n_tot
    print ("Accuracy: %0.02f pct (%d of %d) right"%(acc, n_rig, n_tot))
    for e in tqdm(range(nb_epoch)):
        data_new = produce_data_bacth(BATCH_SIZE)

        # real image
        image_batch=data_new[0]
        # image_batch = X_train[np.random.randint(0,X_train.shape[0],size=BATCH_SIZE),:,:,:]
        losses = {"d":[], "g":[]}
        # generative image
        noise_gen=data_new[1]
        # noise_gen = np.random.uniform(0,1,size=[BATCH_SIZE,100])
        generated_images = generator.predict(noise_gen)

        generator.fit(noise_gen,image_batch, epochs=15, batch_size=128)

        # Train discriminator on generated images
        X = np.concatenate((image_batch, generated_images))
        y = np.zeros([2*BATCH_SIZE,2])
        # one-hot code
        y[0:BATCH_SIZE,1] = 1
        y[BATCH_SIZE:,0] = 1

        make_trainable(discriminator,True)
        d_loss  = discriminator.train_on_batch(X,y)
        losses["d"].append(d_loss)

        # train Generator-Discriminator stack on input noise to non-generated output class
        # noise_tr = np.random.uniform(0,1,size=[BATCH_SIZE,100])
        noise_tr = noise_gen
        y2 = np.zeros([BATCH_SIZE,2])
        y2[:,1] = 1

        make_trainable(discriminator,False)
        #make_trainable(discriminator,False)
        g_loss = GAN.fit(noise_tr, y2 ,epochs=10)
        losses["g"].append(g_loss)

        # Updates plots
        if e%plt_frq==plt_frq-1:
            # plot_loss(losses)
            plot_gen()
        plot_gen(generator)
        save_model(generator,discriminator,GAN)

def predict(generator):
    img=mpimg.imread("./data_test/B.png")
    img=img[:,:,:3]
    new_image=np.zeros(img.shape,dtype=np.float32)
    print(new_image.shape)
    for i in range(ceil(img.shape[0] / WINDOW_WIDTH)):
        for j in range(ceil(img.shape[1]/WINDOW_HEIGHT)):
            source=img[j*WINDOW_HEIGHT:(j+1)*WINDOW_HEIGHT,i*WINDOW_WIDTH:(i+1)*WINDOW_WIDTH]
            previous_shape=source.shape
            source=pad_to_window(source,WINDOW_HEIGHT,WINDOW_WIDTH)
            source=np.array([source])
            r1=generator.predict(source)
            r1=r1[0]
            # r1/=256
            r1=r1[:previous_shape[0],:previous_shape[1],:]
            new_image[j*WINDOW_HEIGHT:(j+1)*WINDOW_HEIGHT,i*WINDOW_WIDTH:(i+1)*WINDOW_WIDTH,:]=r1[:,:,:]

    plot_diff(new_image,img)
    new_image=new_image[:,:,::-1]*256
    cv2.imwrite("./data_test/3140102299_B.png",new_image)

def save_model(generator,discriminator,GAN):
    model_json = generator.to_json()
    with open("generator.json", "w") as json_file:
        json_file.write(model_json)
    # serialize weights to HDF5
    generator.save_weights("generator.h5")

    model_json = discriminator.to_json()
    with open("discriminator.json", "w") as json_file:
        json_file.write(model_json)
    # serialize weights to HDF5
    discriminator.save_weights("discriminator.h5")

    model_json = GAN.to_json()
    with open("GAN.json", "w") as json_file:
        json_file.write(model_json)
    # serialize weights to HDF5
    GAN.save_weights("GAN.h5")

def load_model():
    dropout_rate = 0.25
    opt = Adam(lr=1e-3)
    dopt = Adam(lr=1e-3)

    # load json and create model
    json_file = open('generator.json', 'r')
    loaded_model_json = json_file.read()
    json_file.close()
    generator = model_from_json(loaded_model_json)
    # load weights into new model
    generator.load_weights("generator.h5")
    generator.compile(loss='mean_squared_error', optimizer=opt)

    # try:
    json_file = open('discriminator.json', 'r')
    loaded_model_json = json_file.read()
    json_file.close()
    discriminator = model_from_json(loaded_model_json)
    # load weights into new model
    discriminator.load_weights("discriminator.h5")
    discriminator.compile(loss='categorical_crossentropy', optimizer=dopt)

    json_file = open('GAN.json', 'r')
    loaded_model_json = json_file.read()
    json_file.close()
    GAN = model_from_json(loaded_model_json)
    # load weights into new model
    GAN.load_weights("GAN.h5")
    GAN.compile(loss='categorical_crossentropy', optimizer=opt)


    plot_gen(generator)
    # predict(generator)


    return generator,discriminator,GAN




if __name__ == "__main__":

    img_rows, img_cols = 28, 28

    dropout_rate = 0.25
    opt = Adam(lr=1e-4)
    dopt = Adam(lr=1e-3)

    print("start building the gan")
    generator=build_generative_model()
    quit()
    discriminator=build_discriminative_model()
    # Freeze weights in the discriminator for stacked training

    # Build stacked GAN model
    gan_input = Input(shape=[WINDOW_HEIGHT,WINDOW_WIDTH,3])
    H = generator(gan_input)
    gan_V = discriminator(H)
    GAN = Model(gan_input, gan_V)
    GAN.compile(loss='categorical_crossentropy', optimizer=opt)
    GAN.summary()

    pre_data=produce_data_bacth(200000)
    X_train=pre_data[0]

    for i in range(200):
        generator.fit(pre_data[1],pre_data[0],epochs=1)
        plot_gen(generator)
        save_model(generator,discriminator,GAN)

    ntrain = 100
    trainidx = random.sample(range(0,X_train.shape[0]), ntrain)
    XT = X_train[trainidx,:,:,:]

    print("pre train the discriminator network")
    # Pre-train the discriminator network ...
    noise_gen = pre_data[1][:ntrain]
    generated_images = generator.predict(noise_gen)
    X = np.concatenate((XT, generated_images))
    n = XT.shape[0]
    y = np.zeros([2*n,2])
    y[:n,1] = 1
    y[n:,0] = 1


    make_trainable(discriminator,True)
    discriminator.fit(X,y, nb_epoch=15, batch_size=128)
    y_hat = discriminator.predict(X)

    # Measure accuracy of pre-trained discriminator network
    y_hat_idx = np.argmax(y_hat,axis=1)
    y_idx = np.argmax(y,axis=1)
    diff = y_idx-y_hat_idx
    n_tot = y.shape[0]
    n_rig = (diff==0).sum()
    acc = n_rig*100.0/n_tot
    print ("Accuracy: %0.02f pct (%d of %d) right"%(acc, n_rig, n_tot))

    # set up loss storage vector

    # Train for 6000 epochs at original learning rates
    train_for_n(generator,discriminator,GAN,nb_epoch=10, plt_frq=500,BATCH_SIZE=32)

    # Train for 2000 epochs at reduced learning rates
    opt.lr.set_value(1e-5)
    dopt.lr.set_value(1e-4)
    train_for_n(nb_epoch=2000, plt_frq=500,BATCH_SIZE=32)

    # Train for 2000 epochs at reduced learning rates
    opt.lr.set_value(1e-6)
    dopt.lr.set_value(1e-5)
    train_for_n(nb_epoch=200, plt_frq=500,BATCH_SIZE=32)
